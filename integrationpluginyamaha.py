import nymea
import time
import threading
import json
import requests
import random
import html
from zeroconf import IPVersion, ServiceBrowser, ServiceInfo, Zeroconf
from typing import Callable, List

class ZeroconfDevice(object):
    # To do: replace with nymea serviceBrowser
    def __init__(self, name: str, ip: str, port: int, model: str, id: str) -> None:
        self.name = name
        self.ip = ip
        self.port = port
        self.model = model
        self.id = id

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.__dict__})"

    def __eq__(self, other) -> bool:
        return self is other or self.__dict__ == other.__dict__

class ZeroconfListener(object):
    # To do: replace with nymea serviceBrowser
    """Basic zeroconf listener."""

    def __init__(self, func: Callable[[ServiceInfo], None]) -> None:
        """Initialize zeroconf listener with function callback."""
        self._func = func

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.__dict__})"

    def __eq__(self, other) -> bool:
        return self is other or self.__dict__ == other.__dict__

    def add_service(self, zeroconf: Zeroconf, type: str, name: str) -> None:
        """Callback function when zeroconf service is discovered."""
        self._func(zeroconf.get_service_info(type, name))

thingsAndReceivers = {}

pollTimer = None

playPoll = False

# to do:
# * add discovery of devices on network using nymea framework
# * discovery of zones instead of auto
# * add action play random to browse menu at server level
# * very long lists in browsing: limit to 500 (or so) entries & add option "show all"
#   * "Show all" could have subtext " this action can be slow"
#   * prefix treeInfo with BI- for "browsable item" and EL- for "extend list"

def discoverThings(info):
    if info.thingClassId == receiverThingClassId:


        logger.log("Discovery started for", info.thingClassId)
        discoveredIps = findIps()
        
        for i in range(0, len(discoveredIps)):
            deviceIp = discoveredIps[i]
            rUrl = 'http://' + deviceIp + ':80/YamahaRemoteControl/ctrl'
            body = '<YAMAHA_AV cmd="GET"><System><Config>GetParam</Config></System></YAMAHA_AV>'
            headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
            rr = requests.post(rUrl, headers=headers, data=body)
            pollResponse = rr.text
            if rr.status_code == requests.codes.ok:
                logger.log("Device with IP " + deviceIp + " is a supported Yamaha AVR.")
                # get device info
                stringIndex1 = pollResponse.find("<System_ID>")
                stringIndex2 = pollResponse.find("</System_ID>")
                responseExtract = pollResponse[stringIndex1+11:stringIndex2]
                systemId = responseExtract
                logger.log("System ID:", systemId)
                stringIndex1 = pollResponse.find("<Model_Name>")
                stringIndex2 = pollResponse.find("</Model_Name>")
                responseExtract = pollResponse[stringIndex1+12:stringIndex2]
                modelType = "Yamaha " + responseExtract
                # check if device already known
                exists = False
                for thing in myThings():
                    logger.log("Comparing to existing receivers: is %s a receiver?" % (thing.name))
                    if thing.thingClassId == receiverThingClassId:
                        logger.log("Yes, %s is a receiver." % (thing.name))
                        if thing.paramValue(receiverThingSerialParamTypeId) == systemId:
                            logger.log("Already have receiver with serial number %s in the system: %s" % (systemId, thing.name))
                            exists = True
                        else:
                            logger.log("Thing %s doesn't match with found receiver with serial number %s" % (thing.name, systemId))
                if exists == False: # Receiver doesn't exist yet, so add it
                    thingDescriptor = nymea.ThingDescriptor(receiverThingClassId, modelType)
                    thingDescriptor.params = [
                        nymea.Param(receiverThingSerialParamTypeId, systemId)
                    ]
                    info.addDescriptor(thingDescriptor)
                else: # Receiver already exists, so show it to allow reconfiguration
                    thingDescriptor = nymea.ThingDescriptor(receiverThingClassId, modelType, thingId=thing.id)
                    thingDescriptor.params = [
                        nymea.Param(receiverThingSerialParamTypeId, systemId)
                    ]
                    info.addDescriptor(thingDescriptor)
            else:
                logger.log("Device with IP " + deviceIp + " does not appear to be a supported Yamaha AVR.")
        info.finish(nymea.ThingErrorNoError)

def findIps():
    # To do: in future use nymea capabilities:
    # no need of any external libraries, you can just call "serviceBrowser = hardwareManager.zeroconf.registerServiceBrowser()"
    # and can then loop over "serviceBrowser.entries"# serviceBrowser = hardwareManager.zeroconf.registerServiceBrowser()
    # for i in range(0, len(serviceBrowser.entries)):
    #     logger.log(serviceBrowser.entries[i])
    
    # foreach (const ZeroConfServiceEntry &entry, m_serviceBrowser->serviceEntries()) {
    #     if (entry.hostAddress().protocol() == QAbstractSocket::IPv6Protocol && entry.hostAddress().toString().startsWith("fe80")) {
    #         // We don't support link-local ipv6 addresses yet. skip those entries
    #         continue;
    #     }
    #     QString uuid;
    #     foreach (const QString &txt, entry.txt()) {
    #         if (txt.startsWith("uuid")) {
    #             uuid = txt.split("=").last();
    #             break;
    #         }
    #     }
    #     if (QUuid(uuid) == kodiUuid) {
    #         ipString = entry.hostAddress().toString();
    #         port = entry.port();
    #         break;
    #     }
    # }
    # for now we use zeroconf (def discover & classes ZeroconfDevice & ZeroconfListener) as borrowed from pyvizio

    ipList = discover("_http._tcp.local.", 5)
    logger.log(ipList)

    discoveredIps = []
    for i in range(0, len(ipList)):
        deviceInfo = ipList[i]
        if "Yamaha" in deviceInfo.name:
            discoveredIps.append(deviceInfo.ip)
    return discoveredIps
    
def discover(service_type: str, timeout: int = 5) -> List[ZeroconfDevice]:
    # To do: replace with nymea serviceBrowser
    """From pyvizio: Return all discovered zeroconf services of a given service type over given timeout period."""
    services = []

    def append_service(info: ServiceInfo) -> None:
        """Append discovered zeroconf service to service list."""
        name = info.name[: -(len(info.type) + 1)]
        ip = info.parsed_addresses(IPVersion.V4Only)[0]
        port = info.port
        model = info.properties.get(b"name", "")
        id = info.properties.get(b"id")

        # handle id decode for various discovered use cases
        if isinstance(id, bytes):
            try:
                int(id, 16)
            except Exception:
                id = id.hex()
        else:
            id = None

        service = ZeroconfDevice(name, ip, port, model, id)
        services.append(service)

    zeroconf = Zeroconf()
    ServiceBrowser(zeroconf, service_type, ZeroconfListener(append_service))
    time.sleep(timeout)
    zeroconf.close()

    return services

def setupThing(info):
    if info.thing.thingClassId == receiverThingClassId:
        searchSystemId = info.thing.paramValue(receiverThingSerialParamTypeId)
        logger.log("setupThing called for", info.thing.name, searchSystemId)

        discoveredIps = findIps()
        found = False
        info.thing.setStateValue(receiverUrlStateTypeId, "0.0.0.0")
        
        for i in range(0, len(discoveredIps)):
            deviceIp = discoveredIps[i]
            rUrl = 'http://' + deviceIp + ':80/YamahaRemoteControl/ctrl'
            body = '<YAMAHA_AV cmd="GET"><System><Config>GetParam</Config></System></YAMAHA_AV>'
            headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
            rr = requests.post(rUrl, headers=headers, data=body)
            pollResponse = rr.text
            if rr.status_code == requests.codes.ok:
                logger.log("Device with IP " + deviceIp + " is a supported Yamaha AVR.")
                # get device info
                stringIndex1 = pollResponse.find("<System_ID>")
                stringIndex2 = pollResponse.find("</System_ID>")
                responseExtract = pollResponse[stringIndex1+11:stringIndex2]
                systemId = responseExtract
                logger.log("System ID:", systemId)
                # check if this is the device with the serial number we're looking for
                if systemId == searchSystemId:
                    logger.log("Device with IP " + deviceIp + " is the existing device.")
                    found = True
                    info.thing.setStateValue(receiverUrlStateTypeId, deviceIp)
                    rr2 = rr
            else:
                logger.log("Device with IP " + deviceIp + " does not appear to be a supported Yamaha AVR.")
        if found == True:
            info.thing.setStateValue(receiverConnectedStateTypeId, True)
            pollReceiver(info.thing)
            info.finish(nymea.ThingErrorNoError)
        else:
            info.thing.setStateValue(receiverConnectedStateTypeId, False)
            info.finish(nymea.ThingErrorHardwareFailure, "Error connecting to the device in the network.")
        
        logger.log("Receiver added:", info.thing.name)
        if info.thing.paramValue(receiverThingAddZonesParamTypeId) == True:
            logger.log("Now adding zones for receiver:", info.thing.name)
            setupZones(info.thing, rr2)

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
        deviceIp = parentReceiver.stateValue(receiverUrlStateTypeId)
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
                        exists = True
                    else:
                        logger.log("Thing %s doesn't match with found zone with number %s" % (thing.name, str(zoneNbr)))
                elif thing.thingClassId == receiverThingClassId:
                    logger.log("Yes, %s is a main zone." % (thing.name))
                else:
                     logger.log("No, %s is not a zone." % (thing.name))
            if exists == False: # Zone doesn't exist yet, so add it
                discoveredZones.append(zone)
                zoneName = receiver.name + " Zone " + str(zoneNbr)
                logger.log("Found new additional zone:", zone, zoneNbr)
                logger.log("Adding %s to the system with parent:" % (zoneName), receiver.name, receiver.id)
                thingDescriptor = nymea.ThingDescriptor(zoneThingClassId, zoneName, parentId=receiver.id)
                thingDescriptor.params = [
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
        deviceIp = parentReceiver.stateValue(receiverUrlStateTypeId)
        zoneId = info.paramValue(zoneThingZoneIdParamTypeId)
        logger.log("polling zone", deviceIp, info.name)
        bodyStart = '<YAMAHA_AV cmd="GET"><Zone_' + str(zoneId) + '>'
        bodyEnd = '</Zone_' + str(zoneId) + '></YAMAHA_AV>'
    elif info.thingClassId == receiverThingClassId:
        deviceIp = info.stateValue(receiverUrlStateTypeId)
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
                powerState = False
            elif pollResponse.find("<Power>On</Power>") != -1:
                receiver.setStateValue(receiverPowerStateTypeId, True)
                powerState = True
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
            if plr.status_code == requests.codes.ok and powerState == True:
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
                # Get meta info itemTxtClean = html.unescape(itemTxt)
                stringIndex1 = playerResponse.find("<Artist>")
                stringIndex2 = playerResponse.find("</Artist>")
                responseExtract = playerResponse[stringIndex1+8:stringIndex2]
                receiver.setStateValue(receiverArtistStateTypeId, html.unescape(responseExtract))
                stringIndex1 = playerResponse.find("<Album>")
                stringIndex2 = playerResponse.find("</Album>")
                responseExtract = playerResponse[stringIndex1+7:stringIndex2]
                receiver.setStateValue(receiverCollectionStateTypeId, html.unescape(responseExtract))
                stringIndex1 = playerResponse.find("<Song>")
                stringIndex2 = playerResponse.find("</Song>")
                responseExtract = playerResponse[stringIndex1+6:stringIndex2]
                receiver.setStateValue(receiverTitleStateTypeId, html.unescape(responseExtract))
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
                powerState = False
            elif pollResponse.find("<Power>On</Power>") != -1:
                zone.setStateValue(zonePowerStateTypeId, True)
                powerState = True
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
            if plr.status_code == requests.codes.ok and powerState == True:
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

def executeAction(info):
    pollReceiver(info.thing)
    if info.thing.thingClassId == zoneThingClassId:
        # get parent receiver thing, needed to get deviceIp
        for possibleParent in myThings():
            if possibleParent.id == info.thing.parentId:
                parentReceiver = possibleParent
        deviceIp = parentReceiver.stateValue(receiverUrlStateTypeId)
        zoneId = info.thing.paramValue(zoneThingZoneIdParamTypeId)
        bodyStart = '<YAMAHA_AV cmd="PUT"><Zone_' + str(zoneId) + '>'
        bodyEnd = '</Zone_' + str(zoneId) + '></YAMAHA_AV>'
        source = info.thing.stateValue(zoneInputSourceStateTypeId)
    elif info.thing.thingClassId == receiverThingClassId:
        deviceIp = info.thing.stateValue(receiverUrlStateTypeId)
        bodyStart = '<YAMAHA_AV cmd="PUT"><Main_Zone>'
        bodyEnd = '</Main_Zone></YAMAHA_AV>'
        source = info.thing.stateValue(receiverInputSourceStateTypeId)

    logger.log("executeAction called for thing", info.thing.name, deviceIp, source, info.actionTypeId, info.params)
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
            pr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(0.5)
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
        time.sleep(0.5)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverSkipBackActionTypeId or info.actionTypeId == zoneSkipBackActionTypeId:
        body = '<YAMAHA_AV cmd="PUT"><' + source + '><Play_Control><Playback>Skip Rev</Playback></Play_Control></' + source + '></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(0.5)
        pollReceiver(info.thing)
        # AirPlay statusupdates appear to take a while longer to be available in API
        if source == "AirPlay":
            time.sleep(6)
            pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverStopActionTypeId or info.actionTypeId == zoneStopActionTypeId:
        body = '<YAMAHA_AV cmd="PUT"><' + source + '><Play_Control><Playback>Stop</Playback></Play_Control></' + source + '></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(0.5)
        pollReceiver(info.thing)
        if source == "AirPlay":
            time.sleep(6)
            pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverPlayActionTypeId or info.actionTypeId == zonePlayActionTypeId:
        # power on device first, so action will work when device is off when action is initiated?
        body = '<YAMAHA_AV cmd="PUT"><' + source + '><Play_Control><Playback>Play</Playback></Play_Control></' + source + '></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(0.5)
        pollReceiver(info.thing)
        if source == "AirPlay":
            time.sleep(6)
            pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverPauseActionTypeId or info.actionTypeId == zonePauseActionTypeId:
        body = '<YAMAHA_AV cmd="PUT"><' + source + '><Play_Control><Playback>Pause</Playback></Play_Control></' + source + '></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(0.5)
        pollReceiver(info.thing)
        if source == "AirPlay":
            time.sleep(6)
            pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverSkipNextActionTypeId or info.actionTypeId == zoneSkipNextActionTypeId:
        body = '<YAMAHA_AV cmd="PUT"><' + source + '><Play_Control><Playback>Skip Fwd</Playback></Play_Control></' + source + '></YAMAHA_AV>'
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(0.5)
        pollReceiver(info.thing)
        if source == "AirPlay":
            time.sleep(6)
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
        time.sleep(0.5)
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
        time.sleep(0.5)
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
        time.sleep(0.5)
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
        time.sleep(0.5)
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
        time.sleep(0.5)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverBassActionTypeId:
        bass = str(info.paramValue(receiverBassActionBassParamTypeId))
        logger.log("Bass set to", bass)
        body = bodyStart + '<Sound_Video><Tone><Bass><Val>' + bass + '</Val><Exp>1</Exp><Unit>dB</Unit></Bass></Tone></Sound_Video>' + bodyEnd
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(0.5)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverTrebleActionTypeId:
        treble = str(info.paramValue(receiverTrebleActionTrebleParamTypeId))
        logger.log("Treble set to", treble)
        body = bodyStart + '<Sound_Video><Tone><Treble><Val>' + treble + '</Val><Exp>1</Exp><Unit>dB</Unit></Treble></Tone></Sound_Video>' + bodyEnd
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(0.5)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverInputSourceActionTypeId or info.actionTypeId == zoneInputSourceActionTypeId:
        # power on device first, so action will work when device is off when action is initiated?
        if info.actionTypeId == receiverInputSourceActionTypeId:
            inputSource = info.paramValue(receiverInputSourceActionInputSourceParamTypeId)
        else:
            inputSource = info.paramValue(zoneInputSourceActionInputSourceParamTypeId)
        logger.log("Input Source changed to", inputSource)
        body = bodyStart + '<Input><Input_Sel>' + inputSource + '</Input_Sel></Input>' + bodyEnd
        rr = requests.post(rUrl, headers=headers, data=body)
        time.sleep(0.5)
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
        time.sleep(0.5)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverShuffleActionTypeId or info.actionTypeId == zoneShuffleActionTypeId:
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
        time.sleep(0.5)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverRepeatActionTypeId or info.actionTypeId == zoneRepeatActionTypeId:
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
        time.sleep(0.5)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
        return
    elif info.actionTypeId == receiverRandomAlbumActionTypeId or info.actionTypeId == zoneRandomAlbumActionTypeId:
        playRandomAlbum(rUrl, source)
        time.sleep(0.5)
        pollReceiver(info.thing)
        info.finish(nymea.ThingErrorNoError)
    else:
        logger.log("Action not yet implemented for thing")
        info.finish(nymea.ThingErrorNoError)
        return

def playRandomAlbum(rUrl, source):
    # currently source needs to be SERVER
    # To do: add code to filter out unselectable items
    if source == "SERVER":
        browseTree = ["Random", "Music", "By Album", "Random", "Play"]
        logger.log("Playing random album on source " + source)
    else:
        browseTree = []
        logger.log("Source not supported for this action")
    # go up to the main menu level if needed
    if len(browseTree) > 0:
        selLayer = 1
        browseResponse, menuLayer = browseMenuReady(rUrl, source)
        while menuLayer > selLayer:
            menuLevelUp(rUrl, source)
            browseResponse, menuLayer = browseMenuReady(rUrl, source)
    # navigate browseTree (first item select random server, then folder "Music", ...)
    for i in range (0, len(browseTree)):
        if browseTree[i] == "Random":
            browseResponse, menuLayer = browseMenuReady(rUrl, source)
            currentLine, maxLine = getLineNbrs(browseResponse)
            selItem = random.randint(1, maxLine)
            selectLine(rUrl, source, selItem)
        elif browseTree[i] == "Play":
            selectLine(rUrl, source, 1)
        else:
            selItem = findLine(rUrl, source, browseTree[i])
            selectLine(rUrl, source, selItem)
    return

def findLine(rUrl, source, searchTxt):
    # browse menu level: keep going through menu pages (of 8 items per page) until lineTxt is found
    loop = True
    selItem = 0
    while loop == True:
        browseResponse, menuLayer = browseMenuReady(rUrl, source)
        currentLine, maxLine = getLineNbrs(browseResponse)
        # read the 8 lines in the current browseResponse page
        for i in range(1, 9):
            itemTxt, itemAttr = readLine(browseResponse, i)
            if itemTxt == searchTxt:
                selItem = currentLine + i - 1
                loop = False
        if maxLine > currentLine + 7 and loop == True:
            # end of list not yet reached, go to next page
            pageDown(rUrl, source)
        else:
            # last page, stop loop
            loop = False
    return selItem

def browseThing(browseResult):
    zoneOrReceiver = browseResult.thing
    pollReceiver(zoneOrReceiver)
    if zoneOrReceiver.thingClassId == zoneThingClassId:
        # get parent receiver thing, needed to get deviceIp
        for possibleParent in myThings():
            if possibleParent.id == zoneOrReceiver.parentId:
                parentReceiver = possibleParent
        deviceIp = parentReceiver.stateValue(receiverUrlStateTypeId)
        source = zoneOrReceiver.stateValue(zoneInputSourceStateTypeId)
        playRandomId = zoneRandomAlbumActionTypeId
    elif zoneOrReceiver.thingClassId == receiverThingClassId:
        deviceIp = zoneOrReceiver.stateValue(receiverUrlStateTypeId)
        source = zoneOrReceiver.stateValue(receiverInputSourceStateTypeId)
        playRandomId = receiverRandomAlbumActionTypeId
    rUrl = 'http://' + deviceIp + ':80/YamahaRemoteControl/ctrl'
    maxItems = 24

    if browseResult.itemId == "":
        # go to first menu layer
        selLayer = 1
        selItem = 0
    else:
        selType, selLayer, selItem, selTxt = splitBrowseItem(browseResult.itemId)

    # go up to the selected menu level if needed
    browseResponse, menuLayer = browseMenuReady(rUrl, source)
    while menuLayer > selLayer:
        menuLevelUp(rUrl, source)
        browseResponse, menuLayer = browseMenuReady(rUrl, source)
    
    selectLine(rUrl, source, selItem)

    # browse menu level: keep going through menu pages (of 8 items per page) while last page hasn't been reached
    loop = True
    while loop == True:
        browseResponse, menuLayer = browseMenuReady(rUrl, source)
        currentLine, maxLine = getLineNbrs(browseResponse)
        # read the 8 lines in the current browseResponse page
        for i in range(1, 9):
            itemTxt, itemAttr = readLine(browseResponse, i)
            itemTxtClean = html.unescape(itemTxt)
            treeInfo = "BI-layer-" + str(menuLayer) + "-item-" + str(currentLine+i-1) + "-" + itemTxt
            if itemAttr == "Container":
                browseResult.addItem(nymea.BrowserItem(treeInfo, itemTxtClean, browsable=True, icon=nymea.BrowserIconFavorites))
            elif itemAttr == "Item":
                browseResult.addItem(nymea.BrowserItem(treeInfo, itemTxtClean, executable=True, icon=nymea.BrowserIconFavorites))
            else:
                # found unselectable item, indicating end of list, stop loop
                if len(itemTxt) > 0:
                    browseResult.addItem(nymea.BrowserItem(treeInfo, itemTxt, "Not selectable on this receiver", executable=False, disabled=True, icon=nymea.BrowserIconFavorites))
                else:
                    loop = False
        if maxLine > currentLine + 7 and loop == True:
            # end of list not yet reached, go to next page
            pageDown(rUrl, source)
        else:
            # last page, stop loop
            loop = False
    
    browseResult.finish(nymea.ThingErrorNoError)
    return

def executeBrowserItem(info):
    zoneOrReceiver = info.thing
    pollReceiver(zoneOrReceiver)
    if zoneOrReceiver.thingClassId == zoneThingClassId:
        # get parent receiver thing, needed to get deviceIp
        for possibleParent in myThings():
            if possibleParent.id == zoneOrReceiver.parentId:
                parentReceiver = possibleParent
        deviceIp = parentReceiver.stateValue(receiverUrlStateTypeId)
        source = zoneOrReceiver.stateValue(zoneInputSourceStateTypeId)
    elif zoneOrReceiver.thingClassId == receiverThingClassId:
        deviceIp = zoneOrReceiver.stateValue(receiverUrlStateTypeId)
        source = zoneOrReceiver.stateValue(receiverInputSourceStateTypeId)
    rUrl = 'http://' + deviceIp + ':80/YamahaRemoteControl/ctrl'
    
    selType, selLayer, selItem, selTxt = splitBrowseItem(info.itemId)

    # go up to the selected menu level if needed
    browseResponse, menuLayer = browseMenuReady(rUrl, source)
    while menuLayer > selLayer:
        menuLevelUp(rUrl, source)
        browseResponse, menuLayer = browseMenuReady(rUrl, source)

    selectLine(rUrl, source, selItem)

    info.finish(nymea.ThingErrorNoError)
    time.sleep(0.5)
    pollReceiver(zoneOrReceiver)
    return

def selectLine(rUrl, source, selItem):
    if selItem > 0:
        headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
        gotoLine1(rUrl, source)
        browseResponse, menuLayer = browseMenuReady(rUrl, source)
        currentLine, maxLine = getLineNbrs(browseResponse)
        while selItem > currentLine + 7:
            # jump to the list page with the selected line
            remainder = selItem % 8
            if remainder == 0:
                remainder = 8
            jumpBody = '<YAMAHA_AV cmd="PUT"><SERVER><List_Control><Jump_Line>' + str(selItem - remainder + 1) + '</Jump_Line></List_Control></SERVER></YAMAHA_AV>'
            jr = requests.post(rUrl, headers=headers, data=jumpBody)
            # confirm we got to right page
            browseResponse, menuLayer = browseMenuReady(rUrl, source)
            currentLine, maxLine = getLineNbrs(browseResponse)
        # now select correct line to go to the next menu level
        selectBody = '<YAMAHA_AV cmd="PUT"><' + source + '><List_Control><Direct_Sel>Line_' + str(selItem - currentLine + 1) + '</Direct_Sel></List_Control></' + source + '></YAMAHA_AV>'
        sr = requests.post(rUrl, headers=headers, data=selectBody)
    return

def pageDown(rUrl, source):
    # scroll to next page of list
    headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
    scrollBody = '<YAMAHA_AV cmd="PUT"><' + source + '><List_Control><Page>Down</Page></List_Control></' + source + '></YAMAHA_AV>'
    sr = requests.post(rUrl, headers=headers, data=scrollBody)
    return

def menuLevelUp(rUrl, source):
    headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
    returnBody = '<YAMAHA_AV cmd="PUT"><' + source + '><List_Control><Cursor>Return</Cursor></List_Control></' + source + '></YAMAHA_AV>'
    ur = requests.post(rUrl, headers=headers, data=returnBody)
    return

def readLine(browseResponse, i):
    lineResult = []
    stringIndex1 = browseResponse.find("<Line_" + str(i) + ">")
    stringIndex2 = browseResponse.find("</Line_" + str(i) + ">")
    browseTxt = browseResponse[stringIndex1+8:stringIndex2]
    stringIndex1 = browseTxt.find("<Txt>")
    stringIndex2 = browseTxt.find("</Txt>")
    itemTxt = browseTxt[stringIndex1+5:stringIndex2]
    stringIndex1 = browseTxt.find("<Attribute>")
    stringIndex2 = browseTxt.find("</Attribute>")
    itemAttr = browseTxt[stringIndex1+11:stringIndex2]
    return itemTxt, itemAttr

def splitBrowseItem(itemId):
    splitId = itemId.split("-",5)
    selType = splitId[0]
    selLayer = int(splitId[2])
    selItem = int(splitId[4])
    selTxt = splitId[5]
    return selType, selLayer, selItem, selTxt

def getLineNbrs(browseResponse):
    stringIndex1 = browseResponse.find("<Current_Line>")
    stringIndex2 = browseResponse.find("</Current_Line>")
    currentLine = int(browseResponse[stringIndex1+14:stringIndex2])
    stringIndex1 = browseResponse.find("<Max_Line>")
    stringIndex2 = browseResponse.find("</Max_Line>")
    maxLine = int(browseResponse[stringIndex1+10:stringIndex2])
    return currentLine, maxLine

def gotoLine1(rUrl, source):
    # make sure we are on the first line in the menu before continuing
    headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
    browseBody = '<YAMAHA_AV cmd="GET"><' + source + '><List_Info>GetParam</List_Info></' + source + '></YAMAHA_AV>'   
    browseResponse, menuLayer = browseMenuReady(rUrl, source)
    jumpInt = 1
    jumpBody = '<YAMAHA_AV cmd="PUT"><' + source + '><List_Control><Jump_Line>' + str(jumpInt) + '</Jump_Line></List_Control></' + source + '></YAMAHA_AV>'
    jr = requests.post(rUrl, headers=headers, data=jumpBody)
    return

def browseMenuReady(rUrl, source):
    # make sure menu status is Ready before sending any further commands, as they may not be processed by the receiver
    # at same time, return list info as we got it anyway when checking menu status
    headers = {'Content-Type': 'text/xml', 'Accept': '*/*'}
    browseBody = '<YAMAHA_AV cmd="GET"><' + source + '><List_Info>GetParam</List_Info></' + source + '></YAMAHA_AV>'   
    ready = False
    while ready == False:
        br = requests.post(rUrl, headers=headers, data=browseBody)
        browseResponse = br.text
        stringIndex1 = browseResponse.find("<Menu_Status>")
        stringIndex2 = browseResponse.find("</Menu_Status>")
        menuStatus = browseResponse[stringIndex1+13:stringIndex2]
        if menuStatus == "Ready":
            ready = True
            stringIndex1 = browseResponse.find("<Menu_Layer>")
            stringIndex2 = browseResponse.find("</Menu_Layer>")
            menuLayer = int(browseResponse[stringIndex1+12:stringIndex2])
        else:
            time.sleep(0.1)
    return browseResponse, menuLayer

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