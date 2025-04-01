# This file is for storing data output formatting for F1 2023 game telemetry data

# telemetry setup
udp_port = 20777  # udp telemetry port

PacketHeader = {
    "format": '<HBBBBBQfIIBB',
    "size": 29,
    "fields": [
        "packetFormat", "gameYear", "gameMajorVersion", "gameMinorVersion", "packetVersion", "packetId",
        "sessionUID", "sessionTime", "frameIdentifier", "overallFrameIdentifier", "playerCarIndex", "secondaryPlayerCarIndex" #12
    ]
}

CarTelemetryData = {
    "id": 6,
    "format": '<HfffBbHBBH4H4B4BH4f4B',
    "size": 60,
    "fields": [
        "speed", 
        "throttle", 
        "steer", 
        "brake", 
        "clutch", 
        "gear", 
        "engineRPM", 
        "drs", 
        "revLightsPercent", 
        "revLightsBitValue", 
        "brakesTemperatureRL", "brakesTemperatureRR", "brakesTemperatureFL", "brakesTemperatureFR",
        "tyresSurfaceTemperatureRL", "tyresSurfaceTemperatureRR", "tyresSurfaceTemperatureFL", "tyresSurfaceTemperatureFR",
        "tyresInnerTemperatureRL", "tyresInnerTemperatureRR", "tyresInnerTemperatureFL", "tyresInnerTemperatureFR",
        "engineTemperature", 
        "tyresPressureRL", "tyresPressureRR", "tyresPressureFL", "tyresPressureFR",
        "surfaceTypeRL", "surfaceTypeRR", "surfaceTypeFL", "surfaceTypeFR"
    ]
}

PacketCarTelemetryData = {
    "id": 6,  # Assuming packet ID 6 based on F1 23 telemetry docs
    "format": PacketHeader["format"] + ('HfffBbHBBH4H4B4BH4f4B' * 22) + 'BBb',
    "size": PacketHeader["size"] + (22 * 60) + 3,  # Header size + (22 * size of CarTelemetryData) + 3 bytes for extra fields
    "fields": PacketHeader["fields"] + CarTelemetryData["fields"] * 22 + ["mfdPanelIndex", "mfdPanelIndexSecondaryPlayer", "suggestedGear"],
    "custom_processing": lambda telemetry_name, telemetry_data: ProcessPacketCarTelemetryData(telemetry_name, telemetry_data)
}

def ProcessPacketCarTelemetryData(telemetry_name, telemetry_data):
    if telemetry_name in CarTelemetryData["fields"]: # if in car telemetry data, will need to multiply by playerCarIndex to get our car - thats what this custom processing is for
        telemetry_index = CarTelemetryData["fields"].index(telemetry_name)
        player_car_index = telemetry_data[PacketHeader["fields"].index("playerCarIndex")]
        if player_car_index > 21: #this condition will results in out of range error I think, just printing in case this happens we can track it down
            print("player car index is ", player_car_index)
        value = telemetry_data[len(PacketHeader["fields"]) + (player_car_index * len(CarTelemetryData["fields"])) + telemetry_index] # header + account for which car place we're in + index of telemetry data
        return value
    else:
        #if we're here we are in the lst 3 fields of the packet, just return the value at its index
        return telemetry_data[PacketCarTelemetryData["fields"].index(telemetry_name)]

PacketMotionExData = {
    "id": 13,
    "format": PacketHeader["format"] + '4f4f4f4f4f4f4ffffffffffff4f',
    "size": 188,
    "fields": PacketHeader["fields"] + [
        "suspensionPositionRL", "suspensionPositionRR", "suspensionPositionFL", "suspensionPositionFR",
        "suspensionVelocityRL", "suspensionVelocityRR", "suspensionVelocityFL", "suspensionVelocityFR",
        "suspensionAccelerationRL", "suspensionAccelerationRR", "suspensionAccelerationFL", "suspensionAccelerationFR",
        "wheelSpeedRL", "wheelSpeedRR", "wheelSpeedFL", "wheelSpeedFR",
        "wheelSlipRatioRL", "wheelSlipRatioRR", "wheelSlipRatioFL", "wheelSlipRatioFR",
        "wheelSlipAngleRL", "wheelSlipAngleRR", "wheelSlipAngleFL", "wheelSlipAngleFR",
        "wheelLatForceRL", "wheelLatForceRR", "wheelLatForceFL", "wheelLatForceFR",
        "wheelLongForceRL", "wheelLongForceRR", "wheelLongForceFL", "wheelLongForceFR",
        "heightOfCOGAboveGround", 
        "localVelocityX", "localVelocityY", "localVelocityZ",
        "angularVelocityX", "angularVelocityY", "angularVelocityZ",
        "angularAccelerationX", "angularAccelerationY", "angularAccelerationZ",
        "frontWheelsAngle", 
        "wheelVertForceRL", "wheelVertForceRR", "wheelVertForceFL", "wheelVertForceFR"
    ],
}

#list of packets to read telemetry from
use_packets = [PacketCarTelemetryData, PacketMotionExData]




