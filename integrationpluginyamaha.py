import nymea
import time
import threading
import json
import requests

thingsAndReceivers = {}

pollTimer = None

playPoll = False

def setupThing(info):
    if info.thing.thingClassId == receiverThingClassId:
        logger.log("setupThing called for", info.thing.name)
        
        # discovery of receivers?:
        # import socket
        # print ([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1])

        deviceIp = info.thing.paramValue(receiverThingUrlParamTypeId)
        rUrl = 'http://' + deviceIp + ':80/YamahaRemoteControl/ctrl'
        body = '<YAMAHA_AV cmd="GET"><System><Config>GetParam</Config></System></YAMAHA_AV>'
        headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
        rr = requests.post(rUrl, headers=headers, data=body)
        pollResponse = rr.text

        if rr.status_code == requests.codes.ok:
            logger.log("Device with IP " + deviceIp + " is Yamaha AVR.")
            setupReceiver(info.thing, rr)
            pollReceiver(info.thing)
            info.finish(nymea.ThingErrorNoError)
        else:
            info.finish(nymea.ThingErrorHardwareFailure, "Error connecting to the device in the network.");
        
        logger.log("Receiver added:", info.thing.name)
        if info.thing.paramValue(receiverThingAddZonesParamTypeId) == True:
            logger.log("Now adding zones for receiver:", info.thing.name)
            setupZones(info.thing, rr)

        # If no poll timer is set up yet, start it now
        logger.log("Creating polltimer")
        global pollTimer
        pollTimer = threading.Timer(20, pollService)
        pollTimer.start()
        
        info.finish(nymea.ThingErrorNoError)
        return

    # Setup for the zone
    if info.thing.thingClassId == zoneThingClassId:
        logger.log("SetupThing for zone:", info.thing.name)
        # get parent receiver thing, needed to get deviceIp
        for possibleParent in myThings():
            if possibleParent.id == info.thing.parentId:
                parentReceiver = possibleParent
        deviceIp = parentReceiver.paramValue(receiverThingUrlParamTypeId)
        zoneId = info.thing.paramValue(zoneThingZoneIdParamTypeId)
        zone = "Zone_" + str(zoneId)
        try:
            pollReceiver(info.thing)
            logger.log(zone + " added.")
            info.thing.setStateValue(zoneConnectedStateTypeId, True)
        except:
            logger.warn("Error getting zone state");
            info.finish(nymea.ThingErrorHardwareFailure, "Unable to set up zone.")
            info.thing.setStateValue(zoneConnectedStateTypeId, False)
            return;

        # set up polling for zone status
        info.finish(nymea.ThingErrorNoError)
        return


def setupReceiver(receiver, response):
    pollResponse = response.text
    if response.status_code == requests.codes.ok:
        receiver.setStateValue(receiverConnectedStateTypeId, True)
        # To do: get available features & inputs -- see below for receiver reply with required info; features available for all zones, inputs only for main zone?
        # To do: get available sound programs
        stringIndex1 = pollResponse.find("<System_ID>")
        stringIndex2 = pollResponse.find("</System_ID>")
        responseExtract = pollResponse[stringIndex1+11:stringIndex2]
        systemId = responseExtract
        logger.log("System ID:", systemId)
        stringIndex1 = pollResponse.find("<Model_Name>")
        stringIndex2 = pollResponse.find("</Model_Name>")
        responseExtract = pollResponse[stringIndex1+12:stringIndex2]
        modelType = "Yamaha " + responseExtract
        logger.log("Model type:", modelType)
        # how to save type to thing? (when setting up zones: can be passed on to zone upon auto creation, but would this be useful?)
        # how to list features & inputs?
    else:
        receiver.setStateValue(receiverConnectedStateTypeId, False)

def setupZones(receiver, response):
    pollResponse = response.text
    thingDescriptors = []
    discoveredZones = []
    possibleZones = list(("Zone_2", "Zone_3", "Zone_4"))
                
    for zone in possibleZones:
        stringIndex1 = pollResponse.find("<" + zone + ">")
        stringIndex2 = pollResponse.find("</" + zone + ">")
        zoneFound = int(pollResponse[stringIndex1+8:stringIndex2])
        zoneNbr = int(zone[5:6])
        stringIndex1 = pollResponse.find("<System_ID>")
        stringIndex2 = pollResponse.find("</System_ID>")
        responseExtract = pollResponse[stringIndex1+11:stringIndex2]
        systemId = responseExtract
        if zoneFound == 1:
            logger.log("Additional zone with number %s found." % (str(zoneNbr)))
            # test if zone already exists
            exists = False
            for thing in myThings():
                logger.log("Comparing to existing zones: is %s a zone?" % (thing.name))
                if thing.thingClassId == zoneThingClassId:
                    logger.log("Yes, %s is a zone." % (thing.name))
                    if thing.paramValue(zoneThingSerialParamTypeId) == systemId and thing.paramValue(zoneThingZoneIdParamTypeId) == zoneNbr:
                        logger.log("Already have zone with number %s in the system" % (str(zoneNbr)))
                        # Yep, already here... skip it
                        exists = True
                    else:
                        logger.log("Thing %s doesn't match with found zone with number %s" % (thing.name, str(zoneNbr)))
                elif thing.thingClassId == receiverThingClassId:
                    logger.log("Yes, %s is a main zone." % (thing.name))
                else:
                     logger.log("No, %s is not a zone." % (thing.name))
            if exists == False: # Zone doesn't exist yet, so add it --> Zone was added double, so test this change!
                discoveredZones.append(zone)
                zoneName = receiver.name + " Zone " + str(zoneNbr)
                logger.log("Found new additional zone:", zone, zoneNbr)
                logger.log("Adding %s to the system with parent:" % (zoneName), receiver.name, receiver.id)
                thingDescriptor = nymea.ThingDescriptor(zoneThingClassId, zoneName, parentId=receiver.id)
                deviceIp = "0.0.0.0"
                thingDescriptor.params = [
                    nymea.Param(zoneThingUrlParamTypeId, deviceIp),
                    nymea.Param(zoneThingSerialParamTypeId, systemId),
                    nymea.Param(zoneThingZoneIdParamTypeId, zoneNbr)
                ]
                thingDescriptors.append(thingDescriptor)

    # And let nymea know about all the receiver's zones
    autoThingsAppeared(thingDescriptors)
    logger.log("Discovered zones for receiver:", discoveredZones);

def pollReceiver(info):
    global playPoll
    if info.thingClassId == zoneThingClassId:
        # get parent receiver thing, needed to get deviceIp
        for possibleParent in myThings():
            if possibleParent.id == info.parentId:
                parentReceiver = possibleParent
        deviceIp = parentReceiver.paramValue(receiverThingUrlParamTypeId)
        zoneId = info.paramValue(zoneThingZoneIdParamTypeId)
        logger.log("polling zone", deviceIp, info.name)
        bodyStart = '<YAMAHA_AV cmd="GET"><Zone_' + str(zoneId) + '>'
        bodyEnd = '</Zone_' + str(zoneId) + '></YAMAHA_AV>'
    elif info.thingClassId == receiverThingClassId:
        deviceIp = info.paramValue(receiverThingUrlParamTypeId)
        logger.log("polling receiver", deviceIp, info.name + " Main Zone")
        bodyStart = '<YAMAHA_AV cmd="GET"><Main_Zone>'
        bodyEnd = '</Main_Zone></YAMAHA_AV>'
    rUrl = 'http://' + deviceIp + ':80/YamahaRemoteControl/ctrl'
    body = bodyStart + '<Basic_Status>GetParam</Basic_Status>' + bodyEnd
    headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
    pr = requests.post(rUrl, headers=headers, data=body)
    pollResponse = pr.text
    # add distinction between receiver & zone
    if info.thingClassId == receiverThingClassId:
        receiver = info
        if pr.status_code == requests.codes.ok:
            receiver.setStateValue(receiverConnectedStateTypeId, True)
            # Get power state
            if pollResponse.find("<Power>Standby</Power>") != -1:
                receiver.setStateValue(receiverPowerStateTypeId, False)
            elif pollResponse.find("<Power>On</Power>") != -1:
                receiver.setStateValue(receiverPowerStateTypeId, True)
            else:
                logger.log("Power state not found!")
            # Get mute state
            if pollResponse.find("<Mute>Off</Mute>") != -1:
                receiver.setStateValue(receiverMuteStateTypeId, False)
            elif pollResponse.find("<Mute>On</Mute>") != -1:
                receiver.setStateValue(receiverMuteStateTypeId, True)
            else:
                logger.log("Mute state not found!")
            # Get pure direct state
            if pollResponse.find("<Pure_Direct><Mode>Off</Mode></Pure_Direct>") != -1:
                receiver.setStateValue(receiverPureDirectStateTypeId, False)
            elif pollResponse.find("<Pure_Direct><Mode>On</Mode></Pure_Direct>") != -1:
                receiver.setStateValue(receiverPureDirectStateTypeId, True)
            else:
                logger.log("Pure Direct state not found!")
            # Get enhancer state
            if pollResponse.find("<Enhancer>Off</Enhancer>") != -1:
                receiver.setStateValue(receiverEnhancerStateTypeId, False)
            elif pollResponse.find("<Enhancer>On</Enhancer>") != -1:
                receiver.setStateValue(receiverEnhancerStateTypeId, True)
            else:
                logger.log("Enhancer state not found!")
            # Get input
            stringIndex1 = pollResponse.find("<Input><Input_Sel>")
            stringIndex2 = pollResponse.find("</Input_Sel>")
            inputSource = pollResponse[stringIndex1+18:stringIndex2]
            receiver.setStateValue(receiverInputSourceStateTypeId, inputSource)
            videoSources = ["HDMI1","HDMI2","HDMI3","HDMI4","HDMI5","AV1","AV2","AV3","AV4","AV5","AV6","V-AUX"]
            if inputSource in videoSources:
                receiver.setStateValue(receiverPlayerTypeStateTypeId, "video")
            else:
                receiver.setStateValue(receiverPlayerTypeStateTypeId, "audio")
            # Get sound program
            stringIndex1 = pollResponse.find("<Sound_Program>")
            stringIndex2 = pollResponse.find("</Sound_Program>")
            responseExtract = pollResponse[stringIndex1+15:stringIndex2]
            receiver.setStateValue(receiverSurroundModeStateTypeId, responseExtract)
            # Get volume
            stringIndex1 = pollResponse.find("<Volume><Lvl><Val>")
            responseExtract = pollResponse[stringIndex1+18:stringIndex1+30]
            stringIndex2 = responseExtract.find("</Val>")
            responseExtract = responseExtract[0:stringIndex2]
            volume = int(responseExtract)
            receiver.setStateValue(receiverVolumeStateTypeId, volume)
            # Get bass
            stringIndex1 = pollResponse.find("<Bass><Val>")
            responseExtract = pollResponse[stringIndex1+11:stringIndex1+30]
            stringIndex2 = responseExtract.find("</Val>")
            responseExtract = responseExtract[0:stringIndex2]
            bass = int(responseExtract)
            receiver.setStateValue(receiverBassStateTypeId, bass)
            # Get treble
            stringIndex1 = pollResponse.find("<Treble><Val>")
            responseExtract = pollResponse[stringIndex1+13:stringIndex1+30]
            stringIndex2 = responseExtract.find("</Val>")
            responseExtract = responseExtract[0:stringIndex2]
            treble = int(responseExtract)
            receiver.setStateValue(receiverTrebleStateTypeId, treble)
            # Get player info
            body = '<YAMAHA_AV cmd="GET"><' + inputSource + '><Play_Info>GetParam</Play_Info></' + inputSource + '></YAMAHA_AV>'
            headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
            plr = requests.post(rUrl, headers=headers, data=body)
            if plr.status_code == requests.codes.ok:
                playerResponse = plr.text
                # Get repeat state
                stringIndex1 = playerResponse.find("<Repeat>")
                stringIndex2 = playerResponse.find("</Repeat>")
                responseExtract = playerResponse[stringIndex1+8:stringIndex2]
                if responseExtract not in ["None", "One", "All"]:
                    responseExtract = "None"
                receiver.setStateValue(receiverRepeatStateTypeId, responseExtract)
                # Get shuffle state
                stringIndex1 = playerResponse.find("<Shuffle>")
                stringIndex2 = playerResponse.find("</Shuffle>")
                responseExtract = playerResponse[stringIndex1+9:stringIndex2]
                if responseExtract == "On":
                    shuffleStatus = True
                else:
                    shuffleStatus = False
                receiver.setStateValue(receiverShuffleStateTypeId, shuffleStatus)
                # Get playback state
                stringIndex1 = playerResponse.find("<Playback_Info>")
                stringIndex2 = playerResponse.find("</Playback_Info>")
                responseExtract = playerResponse[stringIndex1+15:stringIndex2]
                if responseExtract == "Play":
                    playStatus = "Playing"
                    playPoll = True or playPoll
                elif responseExtract == "Pause":
                    playStatus = "Paused"
                    playPoll = True or playPoll
                else:
                    playStatus = "Stopped"
                    playPoll = False or playPoll
                receiver.setStateValue(receiverPlaybackStatusStateTypeId, playStatus)
                # Get meta info
                stringIndex1 = playerResponse.find("<Artist>")
                stringIndex2 = playerResponse.find("</Artist>")
                responseExtract = playerResponse[stringIndex1+8:stringIndex2]
                receiver.setStateValue(receiverArtistStateTypeId, responseExtract)
                stringIndex1 = playerResponse.find("<Album>")
                stringIndex2 = playerResponse.find("</Album>")
                responseExtract = playerResponse[stringIndex1+7:stringIndex2]
                receiver.setStateValue(receiverCollectionStateTypeId, responseExtract)
                stringIndex1 = playerResponse.find("<Song>")
                stringIndex2 = playerResponse.find("</Song>")
                responseExtract = playerResponse[stringIndex1+6:stringIndex2]
                receiver.setStateValue(receiverTitleStateTypeId, responseExtract)
                stringIndex1 = playerResponse.find("<URL>")
                stringIndex2 = playerResponse.find("</URL>")
                responseExtract = playerResponse[stringIndex1+5:stringIndex2]
                artURL = 'http://' + deviceIp + ':80' + responseExtract
                receiver.setStateValue(receiverArtworkStateTypeId, artURL)
            else:
                # Playing from external source so no info available 
                receiver.setStateValue(receiverRepeatStateTypeId, "None")
                receiver.setStateValue(receiverShuffleStateTypeId, False)
                receiver.setStateValue(receiverPlaybackStatusStateTypeId, "Stopped")
                receiver.setStateValue(receiverArtistStateTypeId, "")
                receiver.setStateValue(receiverCollectionStateTypeId, "")
                receiver.setStateValue(receiverTitleStateTypeId, "")
                receiver.setStateValue(receiverArtworkStateTypeId, "")
        else:
            receiver.setStateValue(receiverConnectedStateTypeId, False)
        # To do: add states: 3D Cinema DSP, Adaptive DRC, Dialogue Adjust, Dialogue Adjust Level
    elif info.thingClassId == zoneThingClassId:
        zone = info
        if pr.status_code == requests.codes.ok:
            zone.setStateValue(zoneConnectedStateTypeId, True)
            # Get power state
            if pollResponse.find("<Power>Standby</Power>") != -1:
                zone.setStateValue(zonePowerStateTypeId, False)
            elif pollResponse.find("<Power>On</Power>") != -1:
                zone.setStateValue(zonePowerStateTypeId, True)
            else:
                logger.log("Power state not found!")
            # Get mute state
            if pollResponse.find("<Mute>Off</Mute>") != -1:
                zone.setStateValue(zoneMuteStateTypeId, False)
            elif pollResponse.find("<Mute>On</Mute>") != -1:
                zone.setStateValue(zoneMuteStateTypeId, True)
            else:
                logger.log("Mute state not found!")
            # Get input
            stringIndex1 = pollResponse.find("<Input><Input_Sel>")
            stringIndex2 = pollResponse.find("</Input_Sel>")
            inputSource = pollResponse[stringIndex1+18:stringIndex2]
            zone.setStateValue(zoneInputSourceStateTypeId, inputSource)
            videoSources = ["HDMI1","HDMI2","HDMI3","HDMI4","HDMI5","AV1","AV2","AV3","AV4","AV5","AV6","V-AUX"]
            if inputSource in videoSources:
                zone.setStateValue(zonePlayerTypeStateTypeId, "video")
            else:
                zone.setStateValue(zonePlayerTypeStateTypeId, "audio")
            # Get volume
            stringIndex1 = pollResponse.find("<Volume><Lvl><Val>")
            responseExtract = pollResponse[stringIndex1+18:stringIndex1+30]
            stringIndex2 = responseExtract.find("</Val>")
            responseExtract = responseExtract[0:stringIndex2]
            volume = int(responseExtract)
            zone.setStateValue(zoneVolumeStateTypeId, volume)
            # Get player info
            body = '<YAMAHA_AV cmd="GET"><' + inputSource + '><Play_Info>GetParam</Play_Info></' + inputSource + '></YAMAHA_AV>'
            headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
            plr = requests.post(rUrl, headers=headers, data=body)
            if plr.status_code == requests.codes.ok:
                playerResponse = plr.text
                # Get repeat state
                stringIndex1 = playerResponse.find("<Repeat>")
                stringIndex2 = playerResponse.find("</Repeat>")
                responseExtract = playerResponse[stringIndex1+8:stringIndex2]
                if responseExtract not in ["None", "One", "All"]:
                    responseExtract = "None"
                zone.setStateValue(zoneRepeatStateTypeId, responseExtract)
                # Get shuffle state
                stringIndex1 = playerResponse.find("<Shuffle>")
                stringIndex2 = playerResponse.find("</Shuffle>")
                responseExtract = playerResponse[stringIndex1+9:stringIndex2]
                if responseExtract == "On":
                    shuffleStatus = True
                else:
                    shuffleStatus = False
                zone.setStateValue(zoneShuffleStateTypeId, shuffleStatus)
                # Get playback state
                stringIndex1 = playerResponse.find("<Playback_Info>")
                stringIndex2 = playerResponse.find("</Playback_Info>")
                responseExtract = playerResponse[stringIndex1+15:stringIndex2]
                if responseExtract == "Play":
                    playStatus = "Playing"
                    playPoll = True or playPoll
                elif responseExtract == "Pause":
                    playStatus = "Paused"
                    playPoll = True or playPoll
                else:
                    playStatus = "Stopped"
                    playPoll = False or playPoll
                zone.setStateValue(zonePlaybackStatusStateTypeId, playStatus)
                # Get meta info
                stringIndex1 = playerResponse.find("<Artist>")
                stringIndex2 = playerResponse.find("</Artist>")
                responseExtract = playerResponse[stringIndex1+8:stringIndex2]
                zone.setStateValue(zoneArtistStateTypeId, responseExtract)
                stringIndex1 = playerResponse.find("<Album>")
                stringIndex2 = playerResponse.find("</Album>")
                responseExtract = playerResponse[stringIndex1+7:stringIndex2]
                zone.setStateValue(zoneCollectionStateTypeId, responseExtract)
                stringIndex1 = playerResponse.find("<Song>")
                stringIndex2 = playerResponse.find("</Song>")
                responseExtract = playerResponse[stringIndex1+6:stringIndex2]
                zone.setStateValue(zoneTitleStateTypeId, responseExtract)
                stringIndex1 = playerResponse.find("<URL>")
                stringIndex2 = playerResponse.find("</URL>")
                responseExtract = playerResponse[stringIndex1+5:stringIndex2]
                artURL = 'http://' + deviceIp + ':80' + responseExtract
                zone.setStateValue(zoneArtworkStateTypeId, artURL)
            else:
                # Playing from external source so no info available 
                zone.setStateValue(zoneRepeatStateTypeId, "None")
                zone.setStateValue(zoneShuffleStateTypeId, False)
                zone.setStateValue(zonePlaybackStatusStateTypeId, "Stopped")
                zone.setStateValue(zoneArtistStateTypeId, "")
                zone.setStateValue(zoneCollectionStateTypeId, "")
                zone.setStateValue(zoneTitleStateTypeId, "")
                zone.setStateValue(zoneArtworkStateTypeId, "")
        else:
            zone.setStateValue(zoneConnectedStateTypeId, False)


def pollService():
    logger.log("pollService!!!")
    global playPoll
    playPoll = False
    # Poll all receivers we know
    for thing in myThings():
        if thing.thingClassId == receiverThingClassId:
            pollReceiver(thing)
        if thing.thingClassId == zoneThingClassId:
            pollReceiver(thing)
    # restart the timer for next poll (if player is playing, increase poll frequency)
    global pollTimer
    if playPoll == True:
        pollTimer = threading.Timer(10, pollService)
    else:
        pollTimer = threading.Timer(30, pollService)
    pollTimer.start()

# add distinction between receiver & zone
def executeAction(info):
    pollReceiver(info.thing)
    # To do: also add pollService call after actions
    
    if info.thing.thingClassId == zoneThingClassId:
        # get parent receiver thing, needed to get deviceIp
        for possibleParent in myThings():
            if possibleParent.id == info.thing.parentId:
                parentReceiver = possibleParent
        deviceIp = parentReceiver.paramValue(receiverThingUrlParamTypeId)
        zoneId = info.thing.paramValue(zoneThingZoneIdParamTypeId)
        bodyStart = '<YAMAHA_AV cmd="PUT"><Zone_' + str(zoneId) + '>'
        bodyEnd = '</Zone_' + str(zoneId) + '></YAMAHA_AV>'
        source = info.thing.stateValue(zoneInputSourceStateTypeId)
    elif info.thing.thingClassId == receiverThingClassId:
        deviceIp = info.thing.paramValue(receiverThingUrlParamTypeId)
        bodyStart = '<YAMAHA_AV cmd="PUT"><Main_Zone>'
        bodyEnd = '</Main_Zone></YAMAHA_AV>'
        source = info.thing.stateValue(receiverInputSourceStateTypeId)

    logger.log("executeAction called for thing", info.thing.name, deviceIp, info.actionTypeId, info.params)
    logger.log("action related to source:", source)
    rUrl = 'http://' + deviceIp + ':80/YamahaRemoteControl/ctrl'
    headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}

    if info.actionTypeId == receiverIncreaseVolumeActionTypeId or info.actionTypeId == zoneIncreaseVolumeActionTypeId:
        if info.actionTypeId == receiverIncreaseVolumeActionTypeId:
            stepsize = info.paramValue(receiverIncreaseVolumeActionStepParamTypeId)
        else:
            stepsize = info.paramValue(zoneIncreaseVolumeActionStepParamTypeId)
        volumeDelta = stepsize * 10
        while abs(volumeDelta) >= 5:
            if volumeDelta >= 50:
                step = "Up 5 dB"
                volumeDelta -= 50
            elif volumeDelta >= 10:
                step = "Up 1 dB"
                volumeDelta -= 10
            elif volumeDelta >= 5:
                step = "Up"
                volumeDelta -= 5
            else:
                break
            body = bodyStart + '<Volume><Lvl><Val>' + step + '</Val><Exp></Exp><Unit></Unit></Lvl></Volume>' + bodyEnd
            logger.log("Request body:", body)
            pr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(1)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverDecreaseVolumeActionTypeId or info.actionTypeId == zoneDecreaseVolumeActionTypeId:
        if info.actionTypeId == receiverDecreaseVolumeActionTypeId:
            stepsize = info.paramValue(receiverDecreaseVolumeActionStepParamTypeId)
        else:
            stepsize = info.paramValue(zoneDecreaseVolumeActionStepParamTypeId)
        volumeDelta = stepsize * -10
        while abs(volumeDelta) >= 5:
            if volumeDelta <= -50:
                step = "Down 5 dB"
                volumeDelta += 50
            elif volumeDelta <= -10:
                step = "Down 1 dB"
                volumeDelta += 10
            elif volumeDelta <= -5:
                step = "Down"
                volumeDelta += 5
            else:
                break
            body = bodyStart + '<Volume><Lvl><Val>' + step + '</Val><Exp></Exp><Unit></Unit></Lvl></Volume>' + bodyEnd
            pr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(1)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverSkipBackActionTypeId or info.actionTypeId == zoneSkipBackActionTypeId:
        body = '<YAMAHA_AV cmd="PUT"><' + source + '><Play_Control><Playback>Skip Rev</Playback></Play_Control></' + source + '></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(1)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverStopActionTypeId or info.actionTypeId == zoneStopActionTypeId:
        body = '<YAMAHA_AV cmd="PUT"><' + source + '><Play_Control><Playback>Stop</Playback></Play_Control></' + source + '></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(1)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverPlayActionTypeId or info.actionTypeId == zonePlayActionTypeId:
        body = '<YAMAHA_AV cmd="PUT"><' + source + '><Play_Control><Playback>Play</Playback></Play_Control></' + source + '></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(1)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverPauseActionTypeId or info.actionTypeId == zonePauseActionTypeId:
        body = '<YAMAHA_AV cmd="PUT"><' + source + '><Play_Control><Playback>Pause</Playback></Play_Control></' + source + '></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(1)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverSkipNextActionTypeId or info.actionTypeId == zoneSkipNextActionTypeId:
        body = '<YAMAHA_AV cmd="PUT"><' + source + '><Play_Control><Playback>Skip Fwd</Playback></Play_Control></' + source + '></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(1)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverPowerActionTypeId or info.actionTypeId == zonePowerActionTypeId:
        if info.actionTypeId == receiverPowerActionTypeId:
            power = info.paramValue(receiverPowerActionPowerParamTypeId)
        else:
            power = info.paramValue(zonePowerActionPowerParamTypeId)
        if power == True:
            powerString = "On"
        else:
            powerString = "Standby"
        body = bodyStart + '<Power_Control><Power>' + powerString + '</Power></Power_Control>' + bodyEnd
        headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(1)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverMuteActionTypeId or info.actionTypeId == zoneMuteActionTypeId:
        if info.actionTypeId == receiverMuteActionTypeId:
            mute = info.paramValue(receiverMuteActionMuteParamTypeId)
        else:
            mute = info.paramValue(zoneMuteActionMuteParamTypeId)
        if mute == True:
            muteString = "On"
        else:
            muteString = "Off"
        body = bodyStart + '<Volume><Mute>' + muteString + '</Mute></Volume>' + bodyEnd
        headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(1)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverVolumeActionTypeId or info.actionTypeId == zoneVolumeActionTypeId:
        if info.actionTypeId == receiverVolumeActionTypeId:
            newVolume = info.paramValue(receiverVolumeStateTypeId)
        else:
            newVolume = info.paramValue(zoneVolumeStateTypeId)
        volumeString = str(newVolume)
        logger.log("Volume set to", newVolume)
        body = bodyStart + '<Volume><Lvl><Val>' + volumeString + '</Val><Exp>1</Exp><Unit>dB</Unit></Lvl></Volume>' + bodyEnd
        pr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(1)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverPureDirectActionTypeId:
        pureDirect = info.paramValue(receiverPureDirectActionPureDirectParamTypeId)
        if pureDirect == True:
            PureDirectString = "On"
        else:
            PureDirectString = "Off"
        body = bodyStart + '<Sound_Video><Pure_Direct><Mode>' + PureDirectString + '</Mode></Pure_Direct></Sound_Video>' + bodyEnd
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(1)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverEnhancerActionTypeId:
        enhancer = info.paramValue(receiverEnhancerActionEnhancerParamTypeId)
        if enhancer == True:
            enhancerString = "On"
        else:
            enhancerString = "Off"
        body = bodyStart + '<Surround><Program_Sel><Current><Enhancer>' + enhancerString + '</Enhancer></Current></Program_Sel></Surround>' + bodyEnd
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(1)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverBassActionTypeId:
        bass = str(info.paramValue(receiverBassActionBassParamTypeId))
        logger.log("Bass set to", bass)
        body = bodyStart + '<Sound_Video><Tone><Bass><Val>' + bass + '</Val><Exp>1</Exp><Unit>dB</Unit></Bass></Tone></Sound_Video>' + bodyEnd
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(1)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverTrebleActionTypeId:
        treble = str(info.paramValue(receiverTrebleActionTrebleParamTypeId))
        logger.log("Treble set to", treble)
        body = bodyStart + '<Sound_Video><Tone><Treble><Val>' + treble + '</Val><Exp>1</Exp><Unit>dB</Unit></Treble></Tone></Sound_Video>' + bodyEnd
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(1)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverInputSourceActionTypeId or info.actionTypeId == zoneInputSourceActionTypeId:
        if info.actionTypeId == receiverInputSourceActionTypeId:
            inputSource = info.paramValue(receiverInputSourceActionInputSourceParamTypeId)
        else:
            inputSource = info.paramValue(zoneInputSourceActionInputSourceParamTypeId)
        logger.log("Input Source changed to", inputSource)
        body = bodyStart + '<Input><Input_Sel>' + inputSource + '</Input_Sel></Input>' + bodyEnd
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(1)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverSurroundModeActionTypeId:
        surroundMode = info.paramValue(receiverSurroundModeActionSurroundModeParamTypeId)
        logger.log("Surround Mode changed to", surroundMode)
        if surroundMode != "Straight":
            body = bodyStart + '<Surround><Program_Sel><Current><Sound_Program>' + surroundMode + '</Sound_Program></Current></Program_Sel></Surround>' + bodyEnd
        else:
            body = bodyStart + '<Surround><Program_Sel><Current><Straight>On</Straight></Current></Program_Sel></Surround>' + bodyEnd
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(1)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverShuffleActionTypeId or info.actionTypeId == zoneShuffleActionTypeId:
        # Check: shuffle state not stored/reverts?
        if info.actionTypeId == receiverShuffleActionTypeId:
            shuffle = info.paramValue(receiverShuffleActionShuffleParamTypeId)
        else:
            shuffle = info.paramValue(zoneShuffleActionShuffleParamTypeId)
        if shuffle == True:
            shuffleString = "On"
        else:
            shuffleString = "Off"
        body = '<YAMAHA_AV cmd="PUT"><' + source + '><Play_Control><Play_Mode><Shuffle>' + shuffleString + '</Shuffle></Play_Mode></Play_Control></' + source + '></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(1)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverRepeatActionTypeId or info.actionTypeId == zoneRepeatActionTypeId:
        # Check: repeat state not stored/reverts?
        if info.actionTypeId == receiverRepeatActionTypeId:
            repeat = info.paramValue(receiverRepeatActionRepeatParamTypeId)
        else:
            repeat = info.paramValue(zoneRepeatActionRepeatParamTypeId)
        logger.log("Repeat mode:", repeat)
        if repeat == "All":
            repeatString = "All"
        elif repeat == "One":
            repeatString = "One"
        else:
            repeatString = "Off"
        body = '<YAMAHA_AV cmd="PUT"><' + source + '><Play_Control><Play_Mode><Repeat>' + repeatString + '</Repeat></Play_Mode></Play_Control></' + source + '></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(1)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    else:
        logger.log("Action not yet implemented for thing")
        info.finish(nymea.ThingErrorNoError)
        return


def deinit():
    global pollTimer
    # If we started a poll timer, cancel it on shutdown.
    if pollTimer is not None:
        pollTimer.cancel()


def thingRemoved(thing):
    logger.log("removeThing called for", thing.name)
    # Clean up all data related to this thing
    if pollTimer is not None:
        pollTimer.cancel()