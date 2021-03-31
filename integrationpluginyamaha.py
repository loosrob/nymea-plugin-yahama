import nymea
import time
import threading
import json
import requests

thingsAndReceivers = {}

pollTimer = None

def setupThing(info):
    if info.thing.thingClassId == receiverThingClassId:
        logger.log("setupThing called for", info.thing.name)
        
        # Setup for the receiver
        # Idea: add "zone" ThingClass to receiver, with CreateMethod Auto and paramTypes url, zoneName, and devicetype, based on detected zones
        # * Currently only Main Zone is supported; if receiver has 2nd zone, it isn't added at the moment
        # * To identify multiple zones, query during setupReceiver returns <Feature_Existence><Main_Zone>1</Main_Zone><Zone_2>1</Zone_2>...
        # * Or create 2 thing classes, one is the receiver, one for the zone
        #   * and the zone would be of createMethod discovery (see also example onewire sensors?)
        #   * when the user then goes to "add thing -> yamaha zone" then you'd check if there is a received and create a discovery result for every possible zone for every possible receiver
        #   * if there's no receiver set up yet, you'd return an empty result with the message "Please set up a receiver first"
        #   * make sure to set the parentId of the zones to the receivers thingId, so when the user deletes the receiver, it would take the zones down with it
        #   * using parentId properly would also guarantee that setupThing() for the receiver would happen before the setupThing for the zones etc

        deviceIp = info.thing.paramValue(receiverThingUrlParamTypeId)
        rUrl = 'http://' + deviceIp + ':80/YamahaRemoteControl/ctrl'
        body = '<YAMAHA_AV cmd="GET"><System><Config>GetParam</Config></System></YAMAHA_AV>'
        headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
        rr = requests.post(rUrl, headers=headers, data=body)

        if rr.status_code == requests.codes.ok:
            logger.log("Device with IP " + deviceIp + " is Yamaha AVR.")
            setupReceiver(info.thing)
            pollReceiver(info.thing)
            info.finish(nymea.ThingErrorNoError)
        else:
            info.finish(nymea.ThingErrorHarwareFailure, "Error connecting to the device in the network.");

        # If no poll timer is set up yet, start it now
        logger.log("Creating polltimer")
        global pollTimer
        pollTimer = threading.Timer(20, pollService)
        pollTimer.start()
        
        info.finish(nymea.ThingErrorNoError)
        return

def setupReceiver(receiver):
    # this should become setupZone if we want to support multiple zones
    deviceIp = receiver.paramValue(receiverThingUrlParamTypeId)
    logger.log("setting up receiver", deviceIp)
    rUrl = 'http://' + deviceIp + ':80/YamahaRemoteControl/ctrl'
    body = '<YAMAHA_AV cmd="GET"><System><Config>GetParam</Config></System></YAMAHA_AV>'
    headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
    pr = requests.post(rUrl, headers=headers, data=body)
    pollResponse = pr.text
    # logger.log(pollResponse)
    if pr.status_code == requests.codes.ok:
        receiver.setStateValue(receiverConnectedStateTypeId, True)
        # To do: get available features & inputs -- see below for receiver reply with required info; features available for all zones, inputs only for main zone?
        # To do: get available sound programs
        stringIndex1 = pollResponse.find("<Model_Name>")
        stringIndex2 = pollResponse.find("</Model_Name>")
        responseExtract = pollResponse[stringIndex1+12:stringIndex2]
        modelType = "Yamaha " + responseExtract
        logger.log("Model type:", modelType)
        # how to save type to thing? (when setting up zones: can be passed on to zone upon auto creation, but would this be useful?)
        # how to list features & inputs?
    else:
        receiver.setStateValue(receiverConnectedStateTypeId, False)

    # <YAMAHA_AV rsp="GET" RC="0">
    #     <System>
    #         <Config>
    #             <Model_Name>RX-V675</Model_Name>
    #             <System_ID>0B3387D3</System_ID>
    #             <Version>1.93/2.13</Version>
    #             <Feature_Existence>
    #                 <Main_Zone>1</Main_Zone>
    #                 <Zone_2>1</Zone_2>
    #                 <Zone_3>0</Zone_3>
    #                 <Zone_4>0</Zone_4>
    #                 <Tuner>1</Tuner>
    #                 <DAB>0</DAB>
    #                 <HD_Radio>0</HD_Radio>
    #                 <Rhapsody>0</Rhapsody>
    #                 <Napster>1</Napster>
    #                 <SiriusXM>0</SiriusXM>
    #                 <Spotify>1</Spotify>
    #                 <Pandora>0</Pandora>
    #                 <SERVER>1</SERVER>
    #                 <NET_RADIO>1</NET_RADIO>
    #                 <USB>1</USB>
    #                 <iPod_USB>1</iPod_USB> --> not sho(wn in Yamaha app?
    #                 <AirPlay>1</AirPlay>
    #             </Feature_Existence>
    #             <Name>
    #                 <Input>
    #                     <HDMI_1>HDMI1</HDMI_1>
    #                     <HDMI_2>HDMI2</HDMI_2>
    #                     <HDMI_3>HDMI3</HDMI_3>
    #                     <HDMI_4>HDMI4</HDMI_4>
    #                     <HDMI_5>HDMI5</HDMI_5>
    #                     <AV_1>AV1</AV_1>
    #                     <AV_2>AV2</AV_2>
    #                     <AV_3>AV3</AV_3>
    #                     <AV_4>AV4</AV_4>
    #                     <AV_5>AV5</AV_5>
    #                     <AV_6>AV6</AV_6>
    #                     <V_AUX>V-AUX</V_AUX>
    #                     <AUDIO_1>AUDIO1</AUDIO_1>
    #                     <AUDIO_2>AUDIO2</AUDIO_2>
    #                     <USB>USB</USB>
    #                 </Input>
    #             </Name>
    #         </Config>
    #     </System>
    # </YAMAHA_AV>

def pollReceiver(receiver):
    deviceIp = receiver.paramValue(receiverThingUrlParamTypeId)
    logger.log("polling receiver", deviceIp)
    rUrl = 'http://' + deviceIp + ':80/YamahaRemoteControl/ctrl'
    body = '<YAMAHA_AV cmd="GET"><Main_Zone><Basic_Status>GetParam</Basic_Status></Main_Zone></YAMAHA_AV>'
    headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
    pr = requests.post(rUrl, headers=headers, data=body)
    pollResponse = pr.text
    # logger.log(pollResponse)
    if pr.status_code == requests.codes.ok:
        receiver.setStateValue(receiverConnectedStateTypeId, True)
        # Get power state
        if pollResponse.find("<Power>Standby</Power>") != -1:
            receiver.setStateValue(receiverPowerStateTypeId, False)
            logger.log("Power off")
        elif pollResponse.find("<Power>On</Power>") != -1:
            receiver.setStateValue(receiverPowerStateTypeId, True)
            logger.log("Power on")
        else:
            logger.log("Power state not found!")
        # Get mute state
        if pollResponse.find("<Mute>Off</Mute>") != -1:
            receiver.setStateValue(receiverMuteStateTypeId, False)
        elif pollResponse.find("<Mute>On</Mute>") != -1:
            receiver.setStateValue(receiverMuteStateTypeId, True)
        else:
            logger.log("Mute state not found!")
        # Get straight & pure direct state
        if pollResponse.find("<Straight>Off</Straight>") != -1:
            receiver.setStateValue(receiverStraightStateTypeId, False)
        elif pollResponse.find("<Straight>On</Straight>") != -1:
            receiver.setStateValue(receiverStraightStateTypeId, True)
        else:
            logger.log("Straight state not found!")
        if pollResponse.find("<Pure_Direct><Mode>Off</Mode></Pure_Direct>") != -1:
            receiver.setStateValue(receiverPureDirectStateTypeId, False)
        elif pollResponse.find("<Pure_Direct><Mode>On</Mode></Pure_Direct>") != -1:
            receiver.setStateValue(receiverPureDirectStateTypeId, True)
        else:
            logger.log("Straight state not found!")
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
        responseExtract = pollResponse[stringIndex1+18:stringIndex2]
        logger.log("Input source:", responseExtract)
        receiver.setStateValue(receiverInputSourceStateTypeId, responseExtract)
        # Get sound program
        stringIndex1 = pollResponse.find("<Sound_Program>")
        stringIndex2 = pollResponse.find("</Sound_Program>")
        responseExtract = pollResponse[stringIndex1+15:stringIndex2]
        logger.log("Sound program:", responseExtract)
        receiver.setStateValue(receiverSurroundModeStateTypeId, responseExtract)
        # Get volume
        stringIndex1 = pollResponse.find("<Volume><Lvl><Val>")
        responseExtract = pollResponse[stringIndex1+18:stringIndex1+30]
        stringIndex2 = responseExtract.find("</Val>")
        responseExtract = responseExtract[0:stringIndex2]
        volume = int(responseExtract)
        logger.log("Volume:", volume)
        receiver.setStateValue(receiverVolumeStateTypeId, volume)
        # Get bass
        stringIndex1 = pollResponse.find("<Bass><Val>")
        responseExtract = pollResponse[stringIndex1+11:stringIndex1+30]
        stringIndex2 = responseExtract.find("</Val>")
        responseExtract = responseExtract[0:stringIndex2]
        logger.log("Bass:", responseExtract)
        bass = int(responseExtract)
        receiver.setStateValue(receiverBassStateTypeId, bass)
        # Get treble
        stringIndex1 = pollResponse.find("<Treble><Val>")
        responseExtract = pollResponse[stringIndex1+13:stringIndex1+30]
        stringIndex2 = responseExtract.find("</Val>")
        responseExtract = responseExtract[0:stringIndex2]
        logger.log("Treble:", responseExtract)
        treble = int(responseExtract)
        receiver.setStateValue(receiverTrebleStateTypeId, treble)
        
    else:
        receiver.setStateValue(receiverConnectedStateTypeId, False)

    # To do: get states at poll: artist, collection, title, artwork, playerType, playbackStatus, shuffle, repeat
    # To do: Potentially add states: 3D Cinema DSP, Adaptive DRC, Dialogue Adjust, Dialogue Adjust Level


def pollService():
    logger.log("pollService!!!")

    # Poll all receivers we know
    for thing in myThings():
        if thing.thingClassId == receiverThingClassId:
            # deviceIp = thing.paramValue(receiverThingUrlParamTypeId)
            pollReceiver(thing)
    # restart the timer for next poll
    # to do: distinction based on playbackStatus
    global pollTimer
    pollTimer = threading.Timer(20, pollService)
    pollTimer.start()


def executeAction(info):
    deviceIp = info.thing.paramValue(receiverThingUrlParamTypeId)
    logger.log("executeAction called for thing", deviceIp, info.actionTypeId, info.params)

    if info.actionTypeId == receiverIncreaseVolumeActionTypeId:
        # add action
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverDecreaseVolumeActionTypeId:
        # add action
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverSkipBackActionTypeId:
        # add action
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverStopActionTypeId:
        # add action
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverPlayActionTypeId:
        # add action
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverPauseActionTypeId:
        # add action
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverSkipNextActionTypeId:
        # add action
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverPowerActionTypeId:
        rUrl = 'http://' + deviceIp + ':80/YamahaRemoteControl/ctrl'
        power = info.paramValue(receiverPowerActionPowerParamTypeId)
        if power == True:
            powerString = "On"
        else:
            powerString = "Standby"
        body = '<YAMAHA_AV cmd="PUT"><Main_Zone><Power_Control><Power>' + powerString + '</Power></Power_Control></Main_Zone></YAMAHA_AV>'
        headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
        rr = requests.post(rUrl, headers=headers, data=body)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverMuteActionTypeId:
        rUrl = 'http://' + deviceIp + ':80/YamahaRemoteControl/ctrl'
        mute = info.paramValue(receiverMuteActionMuteParamTypeId)
        if mute == True:
            muteString = "On"
        else:
            muteString = "Off"
        body = '<YAMAHA_AV cmd="PUT"><Main_Zone><Volume><Mute>' + powerString + '</Mute></Volume></Main_Zone></YAMAHA_AV>'
        headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
        rr = requests.post(rUrl, headers=headers, data=body)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverVolumeActionTypeId:
        deviceIp = info.thing.paramValue(receiverThingUrlParamTypeId)
        logger.log("polling receiver", deviceIp)
        rUrl = 'http://' + deviceIp + ':80/YamahaRemoteControl/ctrl'
        body = '<YAMAHA_AV cmd="GET"><Main_Zone><Basic_Status>GetParam</Basic_Status></Main_Zone></YAMAHA_AV>'
        headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
        pr = requests.post(rUrl, headers=headers, data=body)
        pollResponse = pr.text
        stringIndex1 = pollResponse.find("<Volume><Lvl><Val>")
        responseExtract = pollResponse[stringIndex1+18:stringIndex1+30]
        stringIndex2 = responseExtract.find("</Val>")
        responseExtract = responseExtract[0:stringIndex2]
        currentVolume = int(responseExtract)
        newVolume = info.paramValue(receiverVolumeStateTypeId)
        volumeDelta = newVolume - currentVolume
        logger.log("Current volume", currentVolume, "Target volume", newVolume)
        while abs(volumeDelta) > 5:
            logger.log("Volume delta", volumeDelta)
            if volumeDelta >= 50:
                step = "Up 5 dB"
                volumeDelta -= 50
            elif volumeDelta >= 10:
                step = "Up 1 dB"
                volumeDelta -= 10
            elif volumeDelta <= -50:
                step = "Down 5 dB"
                volumeDelta += 50
            elif volumeDelta <= -10:
                step = "Down 1 dB"
                volumeDelta += 10
            else:
                break
            body = '<YAMAHA_AV cmd="PUT"><Main_Zone><Volume><Lvl><Val>' + step + '</Val><Exp></Exp><Unit></Unit></Lvl></Volume></Main_Zone></YAMAHA_AV>'
            logger.log("Request body:", body)
            pr = requests.post(rUrl, headers=headers, data=body)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverPureDirectActionTypeId:
        # add action
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverBassActionTypeId:
        # add action
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverTrebleActionTypeId:
        # add action
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverInputSourceActionTypeId:
        # add action
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverShuffleActionTypeId:
        # Check: shuffle state not stored/reverts?
        rUrl = 'http://' + deviceIp + ':80/YamahaRemoteControl/ctrl'
        shuffle = info.paramValue(receiverShuffleActionShuffleParamTypeId)
        if shuffle == True:
            shuffleString = "On"
        else:
            shuffleString = "Off"
        body = '<YAMAHA_AV cmd="PUT"><SERVER><Play_Control><Play_Mode><Shuffle>' + shuffleString + '</Shuffle></Play_Mode></Play_Control></SERVER></YAMAHA_AV>'
        headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
        rr = requests.post(rUrl, headers=headers, data=body)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverRepeatActionTypeId:
        # Check: repeat state not stored/reverts?
        rUrl = 'http://' + deviceIp + ':80/YamahaRemoteControl/ctrl'
        repeat = info.paramValue(receiverRepeatActionRepeatParamTypeId)
        logger.log("Repeat mode:", repeat)
        if repeat == "All":
            repeatString = "All"
        elif repeat == "One":
            repeatString = "One"
        else:
            repeatString = "Off"
        body = '<YAMAHA_AV cmd="PUT"><SERVER><Play_Control><Play_Mode><Repeat>' + repeatString + '</Repeat></Play_Mode></Play_Control></SERVER></YAMAHA_AV>'
        headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
        rr = requests.post(rUrl, headers=headers, data=body)
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


# $CMD_SetServer = '<YAMAHA_AV cmd="PUT"><Main_Zone><Input><Input_Sel>SERVER</Input_Sel></Input></Main_Zone></YAMAHA_AV>';
# $CMD_SetTuner = '<YAMAHA_AV cmd="PUT"><Main_Zone><Input><Input_Sel>TUNER</Input_Sel></Input></Main_Zone></YAMAHA_AV>';
# $CMD_SetUSB = '<YAMAHA_AV cmd="PUT"><Main_Zone><Input><Input_Sel>USB</Input_Sel></Input></Main_Zone></YAMAHA_AV>';
# $CMD_SetStopItem =	'<YAMAHA_AV cmd="PUT"><SERVER><Play_Control><Playback>Stop</Playback></Play_Control></SERVER></YAMAHA_AV>';
# $CMD_SetRevItem =	'<YAMAHA_AV cmd="PUT"><SERVER><Play_Control><Playback>Skip Rev</Playback></Play_Control></SERVER></YAMAHA_AV>';
# $CMD_SetFwdItem =	'<YAMAHA_AV cmd="PUT"><SERVER><Play_Control><Playback>Skip Fwd</Playback></Play_Control></SERVER></YAMAHA_AV>';