import socket
import struct
import logging
import threading
import time

# This is the processing file for the telemetry data and effects

# This is the amplitude calculation
def amplitude_calc(effect, input): # Effect is the effect object, input is the telemetry value
    min_input = float(effect.min_input_entry.get())
    max_input = float(effect.max_input_entry.get())
    min_amplitude = float(effect.min_amplitude_entry.get())
    max_amplitude = float(effect.max_output_amplitude_slider.get())
    output_expo = float(effect.output_expo.get())  # Get the exponent value
    
    normalized_input = max(0, min(1, (input - min_input) / (max_input - min_input)))
    amplitude = (
                    0 if input < min_input else
                    min_amplitude + (max_amplitude - min_amplitude) * (normalized_input ** output_expo)
                )
    return amplitude


# Trigger Effect Thread
def trigger_effect_handler(input, effect_name, effect, glob_data):
    print(f"pulseduration: {effect.pulse_duration_entry.get()}")
    print(f"effect_name: {effect_name}")
    with glob_data.lock:         
        glob_data.audio[effect_name]['amplitude'] = effect.max_output_amplitude_slider.get() # Trigger the effect                  
        glob_data.audio[effect_name]['prev_gear'] = input # Update prev_gear
    
    def reset_amplitude(effect_name):
        with glob_data.lock:
            glob_data.audio[effect_name]['amplitude'] = 0
    threading.Timer(float(effect.pulse_duration_entry.get()), lambda: reset_amplitude(effect_name)).start()
    
    

def effects_processing(app, glob_data, game_file):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print('udp port is ', game_file.udp_port)
    sock.bind(('localhost', game_file.udp_port))
    sock.settimeout(0.01)  # non-blocking mode

    def read_udp_data():
        try:
            data, _ = sock.recvfrom(2048)   # 2048 is the buffer size - adjustable based on expected packet size
            if len(data) < game_file.PacketHeader['size']:  # At least a complete header to get the packet_id
                return False
            header = struct.unpack_from(game_file.PacketHeader['format'], data)
            #print('player car index is ', header[5])
            packet_id = header[game_file.PacketHeader['fields'].index('packetId')]
            for packet in game_file.use_packets:
                if packet["id"] == packet_id:
                    #print('packet is, ', packet["id"])
                    if len(data) < packet['size']:
                        print('size error')
                        return False
                    packet_data = struct.unpack_from(packet['format'], data)
                    
                    #print(packet_data[10])
                    with glob_data.lock:
                        if packet_id not in glob_data.telemetry:
                            glob_data.telemetry[packet_id] = {}
                        glob_data.telemetry[packet_id] = packet_data  # Store the packet data in the shared state telemetry variable
                    return True
            return False  # Return false if packet_id is not in the packets list
        except socket.timeout:
            return False

    def update_effects():
        for effect_name, effect in app.effects.items():
            if not effect.enable_var.get(): # Turn off the effect if effect_enabled is set to False
                with glob_data.lock: # Update or create any variables required for the audio
                    if effect_name not in glob_data.audio:
                        glob_data.audio[effect_name] = {}
                    glob_data.audio[effect_name]['amplitude'] = 0   
                continue
            # Read the telemetry values using the index
            input_vals = []
            for telemetry_input in effect.telemetry_inputs:
                packet_id = glob_data.game_info['telemetry_options'].get(telemetry_input.get())
                if packet_id in glob_data.telemetry:
                    packet_data = glob_data.telemetry[packet_id]  # This is the data - now read what you want from it
                    for packet in game_file.use_packets:
                        if packet["id"] == packet_id:
                            if 'custom_processing' in packet:
                                input_vals.append(packet['custom_processing'](telemetry_input.get(), packet_data))  # run the custom processing function if there is one
                            else:
                                input_vals.append(packet_data[packet['fields'].index(telemetry_input.get())]) # get the field index and read from the packet - default behaviour
                else:
                    logging.warning(f"Telemetry data for packet_id {packet_id} not found in glob_data.telemetry")

            if not input_vals:
                logging.warning(f"No telemetry inputs found for effect {effect_name}")
                continue  # Skip processing this effect if no telemetry inputs are found

            # Use the process method to determine the input_value
            if effect.process_method_dropdown.get() == 'max':
                input = abs(max(input_vals, key=abs))
            elif effect.process_method_dropdown.get() == 'min':
                input = abs(min(input_vals, key=abs))
            elif effect.process_method_dropdown.get() == 'average':
                input = abs(sum(input_vals, key=abs)) / len(input_vals) if input_vals else 0
            elif effect.process_method_dropdown.get() == 'change':
                input = input_vals[0]  # Only one input value is expected
            else:
                raise ValueError(f"Unknown process method: {effect.process_method_dropdown.get()}")

            
            app.effects[effect_name].plot_data.append(input) # Append the input value to the plot_data list
            
            
            if effect.effect_type == 'range_effect':
                amplitude = amplitude_calc(effect, input) # Calculate the amplitude of the effect based on the input value

                with glob_data.lock:
                    if effect_name not in glob_data.audio:
                        glob_data.audio[effect_name] = {}
                    glob_data.audio[effect_name]['amplitude'] = amplitude

                logging.debug(f"Effect {effect_name} amplitude updated to {amplitude}")

            elif effect.effect_type == 'trigger_effect':
                with glob_data.lock:
                    if effect_name not in glob_data.audio:
                        glob_data.audio[effect_name] = {}
                    prev_gear = glob_data.audio[effect_name].setdefault('prev_gear', input) # Get the previous gear value, write input to it if it doesn't exist
                
                if prev_gear != input:      
                    print("gear change triggered!")
                    trigger_effect_handler(input, effect_name, effect, glob_data)
        
            else:
                raise ValueError(f"Unknown effect type: {effect['type']}")

    last_update_time = time.time()

    # Loop forever unless the stop_thread flag is set to True
    while glob_data.game_info["stop_thread"] == False:
        if read_udp_data():
            last_update_time = time.time()
            update_effects()
        else:
            if time.time() - last_update_time > 0.1: # pause after 0.1 seconds of no data     
                if any(glob_data.audio.get(effect_name, {}).get('amplitude', 0) != 0 for effect_name in app.effects.keys()): # Check if any effect is still active. I guess this makes sure that this only runs once
                    print("game paused")
                    with glob_data.lock:
                        for effect_name in app.effects.keys():
                            if effect_name not in glob_data.audio:
                                glob_data.audio[effect_name] = {}
                            glob_data.audio[effect_name]['amplitude'] = 0
    
    try: # Close the socket if it is still open, before exiting the function
            sock.getsockname()  # Checks if the socket is still bound
            sock.close()
            print("Closed the socket")
    except (NameError, OSError):
        pass  # The socket is already closed or not defined