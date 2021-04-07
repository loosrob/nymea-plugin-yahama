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
    global playPoll
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
        # logger.log("Bass:", responseExtract)
        bass = int(responseExtract)
        receiver.setStateValue(receiverBassStateTypeId, bass)
        # Get treble
        stringIndex1 = pollResponse.find("<Treble><Val>")
        responseExtract = pollResponse[stringIndex1+13:stringIndex1+30]
        stringIndex2 = responseExtract.find("</Val>")
        responseExtract = responseExtract[0:stringIndex2]
        # logger.log("Treble:", responseExtract)
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
            if responseExtract == "Off": responseExtract = "None"
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
                playPoll = True
            elif responseExtract == "Pause":
                playStatus = "Paused"
                playPoll = True
            else:
                playStatus = "Stopped"
                playPoll = False
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

def pollService():
    logger.log("pollService!!!")
    # Poll all receivers we know
    for thing in myThings():
        if thing.thingClassId == receiverThingClassId:
            # deviceIp = thing.paramValue(receiverThingUrlParamTypeId)
            pollReceiver(thing)
    # restart the timer for next poll (if player is playing, increase poll frequency)
    global pollTimer
    if playPoll == True:
        pollTimer = threading.Timer(20, pollService)
    else:
        pollTimer = threading.Timer(60, pollService)
    pollTimer.start()


def executeAction(info):
    # To do: add pollService call after some actions? --> pollReceiver(info.thing)
    deviceIp = info.thing.paramValue(receiverThingUrlParamTypeId)
    logger.log("executeAction called for thing", deviceIp, info.actionTypeId, info.params)
    rUrl = 'http://' + deviceIp + ':80/YamahaRemoteControl/ctrl'
    headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}

    if info.actionTypeId == receiverIncreaseVolumeActionTypeId:
        stepsize = info.paramValue(receiverIncreaseVolumeActionStepParamTypeId)
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
            body = '<YAMAHA_AV cmd="PUT"><Main_Zone><Volume><Lvl><Val>' + step + '</Val><Exp></Exp><Unit></Unit></Lvl></Volume></Main_Zone></YAMAHA_AV>'
            pr = requests.post(rUrl, headers=headers, data=body)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverDecreaseVolumeActionTypeId:
        stepsize = info.paramValue(receiverDecreaseVolumeActionStepParamTypeId)
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
            body = '<YAMAHA_AV cmd="PUT"><Main_Zone><Volume><Lvl><Val>' + step + '</Val><Exp></Exp><Unit></Unit></Lvl></Volume></Main_Zone></YAMAHA_AV>'
            pr = requests.post(rUrl, headers=headers, data=body)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverSkipBackActionTypeId:
        body = '<YAMAHA_AV cmd="PUT"><SERVER><Play_Control><Playback>Skip Rev</Playback></Play_Control></SERVER></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverStopActionTypeId:
        body = '<YAMAHA_AV cmd="PUT"><SERVER><Play_Control><Playback>Stop</Playback></Play_Control></SERVER></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverPlayActionTypeId:
        body = '<YAMAHA_AV cmd="PUT"><SERVER><Play_Control><Playback>Play</Playback></Play_Control></SERVER></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverPauseActionTypeId:
        body = '<YAMAHA_AV cmd="PUT"><SERVER><Play_Control><Playback>Pause</Playback></Play_Control></SERVER></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverSkipNextActionTypeId:
        body = '<YAMAHA_AV cmd="PUT"><SERVER><Play_Control><Playback>Skip Fwd</Playback></Play_Control></SERVER></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverPowerActionTypeId:
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
        mute = info.paramValue(receiverMuteActionMuteParamTypeId)
        if mute == True:
            muteString = "On"
        else:
            muteString = "Off"
        body = '<YAMAHA_AV cmd="PUT"><Main_Zone><Volume><Mute>' + muteString + '</Mute></Volume></Main_Zone></YAMAHA_AV>'
        headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
        rr = requests.post(rUrl, headers=headers, data=body)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverVolumeActionTypeId:
        newVolume = info.paramValue(receiverVolumeStateTypeId)
        volumeString = str(newVolume)
        logger.log("Treble set to", newVolume)
        body = '<YAMAHA_AV cmd="PUT"><Main_Zone><Volume><Lvl><Val>' + volumeString + '</Val><Exp>1</Exp><Unit>dB</Unit></Lvl></Volume></Main_Zone></YAMAHA_AV>'
        pr = requests.post(rUrl, headers=headers, data=body)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverPureDirectActionTypeId:
        pureDirect = info.paramValue(receiverPureDirectActionPureDirectParamTypeId)
        if pureDirect == True:
            PureDirectString = "On"
        else:
            PureDirectString = "Off"
        body = '<YAMAHA_AV cmd="PUT"><Main_Zone><Sound_Video><Pure_Direct><Mode>' + PureDirectString + '</Mode></Pure_Direct></Sound_Video></Main_Zone></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverEnhancerActionTypeId:
        enhancer = info.paramValue(receiverEnhancerActionEnhancerParamTypeId)
        if enhancer == True:
            enhancerString = "On"
        else:
            enhancerString = "Off"
        body = '<YAMAHA_AV cmd="PUT"><Main_Zone><Surround><Program_Sel><Current><Enhancer>' + enhancerString + '</Enhancer></Current></Program_Sel></Surround></Main_Zone></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverBassActionTypeId:
        bass = str(info.paramValue(receiverBassActionBassParamTypeId))
        logger.log("Bass set to", bass)
        body = '<YAMAHA_AV cmd="PUT"><Main_Zone><Sound_Video><Tone><Bass><Val>' + bass + '</Val><Exp>1</Exp><Unit>dB</Unit></Bass></Tone></Sound_Video></Main_Zone></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        return
    elif info.actionTypeId == receiverTrebleActionTypeId:
        treble = str(info.paramValue(receiverTrebleActionTrebleParamTypeId))
        logger.log("Treble set to", treble)
        body = '<YAMAHA_AV cmd="PUT"><Main_Zone><Sound_Video><Tone><Treble><Val>' + treble + '</Val><Exp>1</Exp><Unit>dB</Unit></Treble></Tone></Sound_Video></Main_Zone></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        return
    elif info.actionTypeId == receiverInputSourceActionTypeId:
        inputSource = info.paramValue(receiverInputSourceActionInputSourceParamTypeId)
        logger.log("Input Source changed to", inputSource)
        body = '<YAMAHA_AV cmd="PUT"><Main_Zone><Input><Input_Sel>' + inputSource + '</Input_Sel></Input></Main_Zone></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverSurroundModeActionTypeId:
        surroundMode = info.paramValue(receiverSurroundModeActionSurroundModeParamTypeId)
        logger.log("Surround Mode changed to", surroundMode)
        if surroundMode != "Straight":
            body = '<YAMAHA_AV cmd="PUT"><Main_Zone><Surround><Program_Sel><Current><Sound_Program>' + surroundMode + '</Sound_Program></Current></Program_Sel></Surround></Main_Zone></YAMAHA_AV>'
        else:
            body = '<YAMAHA_AV cmd="PUT"><Main_Zone><Surround><Program_Sel><Current><Straight>On</Straight></Current></Program_Sel></Surround></Main_Zone></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverShuffleActionTypeId:
        # Check: shuffle state not stored/reverts?
        shuffle = info.paramValue(receiverShuffleActionShuffleParamTypeId)
        if shuffle == True:
            shuffleString = "On"
        else:
            shuffleString = "Off"
        body = '<YAMAHA_AV cmd="PUT"><SERVER><Play_Control><Play_Mode><Shuffle>' + shuffleString + '</Shuffle></Play_Mode></Play_Control></SERVER></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverRepeatActionTypeId:
        # Check: repeat state not stored/reverts?
        repeat = info.paramValue(receiverRepeatActionRepeatParamTypeId)
        logger.log("Repeat mode:", repeat)
        if repeat == "All":
            repeatString = "All"
        elif repeat == "One":
            repeatString = "One"
        else:
            repeatString = "Off"
        body = '<YAMAHA_AV cmd="PUT"><SERVER><Play_Control><Play_Mode><Repeat>' + repeatString + '</Repeat></Play_Mode></Play_Control></SERVER></YAMAHA_AV>'
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