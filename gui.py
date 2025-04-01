import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk
import json
import os
import audio
import importlib
import threading
from collections import deque
from globdata import glob_data
import processing
import numpy as np

# This module handles the GUI for the application using customtkinter.

udp_thread = None  # Initialize udp_thread

telemetry_process_options = {
    "range_effect": ["max", "min", "average"],
    "trigger_effect": ["change"]
}

# Function to load telemetry options from a game file
def load_telemetry_options(game_file):
    field_packet_map = {}  # Dictionary to store field -> packet_id mapping
    for packet in game_file.use_packets:
        for field in packet['fields']:
            if field not in field_packet_map: # If the field is not already in the dictionary, add it
                field_packet_map[field] = packet['id']# Dictionary keys are field names and values are their corresponding packet_id
                                       
    with glob_data.lock:
        glob_data.game_info["telemetry_options"] = field_packet_map
    print(f"Game Telemetry Options: {list(glob_data.game_info.get('telemetry_options', {}).keys())}")


# Initialize app
ctk.set_appearance_mode("Dark")  # Default theme
ctk.set_default_color_theme("blue")

class BassShakerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("ShakeLab")
        self.geometry("1100x700")

        self.effects = {}  # Store effect settings

        # Top Menu
        top_frame = ctk.CTkFrame(self)
        top_frame.pack(fill="x", padx=10, pady=5)

        # Dropdown for game files
        self.game_files = self.get_game_files()
        self.selected_game_file = ctk.StringVar()  # Store the selected file name
        self.game_file_dropdown = ctk.CTkComboBox(top_frame, variable=self.selected_game_file, values=self.game_files, command=self.on_game_file_selected)
        self.game_file_dropdown.pack(side="left", padx=5)

        self.load_button = ctk.CTkButton(top_frame, text="Load Settings", command=self.load_settings)
        self.load_button.pack(side="left", padx=5)

        self.save_button = ctk.CTkButton(top_frame, text="Save Settings", command=self.save_settings)
        self.save_button.pack(side="left", padx=5)

        # Effect List
        self.effect_list_frame = ctk.CTkScrollableFrame(self)
        self.effect_list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Add Effect Button and Effect Type Dropdown 
        self.add_effect_button = ctk.CTkButton(self, text="Add Effect", command=self.add_effect)
        self.add_effect_button.pack(side="right", padx=5, pady=5)

        self.effect_type_var = ctk.StringVar(value="range_effect")
        self.effect_type_dropdown = ctk.CTkComboBox(self, variable=self.effect_type_var, values=["range_effect", "trigger_effect"])
        self.effect_type_dropdown.pack(side="right", padx=5, pady=5)

        # Audio Device Selection
        audio_device_label = ctk.CTkLabel(self, text="Audio Device:")
        audio_device_label.pack(side="left", padx=5, pady=5)

        self.audio_devices = audio.get_audio_devices()
        self.audio_devices_formatted = audio.get_audio_devices_formatted()
        self.audio_device_map = {v: k for k, v in self.audio_devices_formatted.items()}  # Map values to indices
        self.selected_audio_device = ctk.StringVar()
        self.audio_device_dropdown = ctk.CTkComboBox(self, variable=self.selected_audio_device, values=list(self.audio_devices_formatted.values()), command=self.on_audio_device_selected)
        self.audio_device_dropdown.pack(side="left", padx=0, pady=5)

        # Add buffer size selection
        buffer_label = ctk.CTkLabel(self, text="Buffer:")
        buffer_label.pack(side="left", padx=5, pady=5)

        self.buffer_size_var = ctk.StringVar(value="128")
        self.buffer_size_dropdown = ctk.CTkComboBox(self, variable=self.buffer_size_var, values=["64", "128", "256", "512", "1024"], command=self.on_buffer_size_selected, width=70)
        self.buffer_size_dropdown.pack(side="left", padx=0, pady=5)
    
        # Add recording button
        self.record_button = ctk.CTkButton(self, text="Rec", fg_color="grey", width=50, height=30, command=self.toggle_recording)
        self.record_button.pack(side="left", padx=10, pady=10)

        # Add start/stop plots button
        self.plotting = False
        self.plot_button = ctk.CTkButton(self, text="Start Plots", fg_color="grey", width=100, height=30, command=self.toggle_plots)
        self.plot_button.pack(side="left", padx=10, pady=10)

    def add_effect(self, effect_data=None):
        effect_id = f"effect{len(self.effects) + 1}"
        effect_type = self.effect_type_var.get() if not effect_data else effect_data.get("effect_type", "range_effect")
        effect = EffectFrame(self.effect_list_frame, effect_id, self.remove_effect, effect_type)
        effect.pack(fill="x", pady=5)
        self.effects[effect_id] = effect

        if effect_data:  # Load existing settings
            effect.load_data(effect_data)

    def remove_effect(self, effect_id):
        if effect_id in self.effects:
            self.effects[effect_id].destroy()
            del self.effects[effect_id]

    
    def load_settings(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if not file_path:
            return
        with open(file_path, "r") as file:
            data = json.load(file)
            # Create a popup window with checkboxes using customtkinter
            popup = ctk.CTkToplevel(self)
            popup.title("Select Options to Load")
            popup.geometry("300x200")
            popup.transient(self)  # Keep the popup in front of the main window
            popup.grab_set()  # Make the popup modal

            load_game_file_var = ctk.BooleanVar(value=True)
            load_audio_device_var = ctk.BooleanVar(value=True)
            load_effects_var = ctk.BooleanVar(value=True)

            ctk.CTkCheckBox(popup, text="Load Game File", variable=load_game_file_var).pack(anchor="w", padx=10, pady=5)
            ctk.CTkCheckBox(popup, text="Load Effects", variable=load_effects_var).pack(anchor="w", padx=10, pady=5)
            ctk.CTkCheckBox(popup, text="Load Audio Device", variable=load_audio_device_var).pack(anchor="w", padx=10, pady=5)
            
            def on_confirm():
                if load_game_file_var.get():
                    game_file = data.get("game_file", "")  # Load Game File
                    if game_file in self.game_files:
                        self.selected_game_file.set(game_file)  # Set dropdown value
                        self.on_game_file_selected(game_file)  # Call the function to load the telemetry options
                    else:
                        messagebox.showwarning(
                            "Game File Not Found",
                            f"The saved game file '{game_file}' was not found. Please make sure the game file is available in the game_files directory."
                        )
                        return

                if load_effects_var.get():
                    for widget in self.effect_list_frame.winfo_children():
                        widget.destroy()
                    self.effects = {}
                    for effect_id, effect_data in data.get("effects", {}).items():  # Load Effects
                        print(f"Loading effect: {effect_id}")
                        self.add_effect(effect_data)

                if load_audio_device_var.get():
                    audio_device = data.get("audio_device", "")  # Load Audio Device
                    if audio_device in list(self.audio_devices_formatted.values()):
                        self.selected_audio_device.set(audio_device)
                        self.on_audio_device_selected(audio_device)
                    else:
                        messagebox.showwarning(
                            "Audio Device Not Found",
                            f"The saved audio device '{audio_device}' was not found. Please make sure the audio device is available and try again"
                        )
                        return

                popup.destroy()

            ctk.CTkButton(popup, text="Confirm", command=on_confirm).pack(pady=10)

    def save_settings(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if not file_path:
            return

        data = {
            "game_file": self.game_file_dropdown.get(),
            "audio_device": self.audio_device_dropdown.get(),
            "effects": {key: effect.get_data() for key, effect in self.effects.items()}
        }

        with open(file_path, "w") as file:
            json.dump(data, file, indent=4)

        with open(file_path, "w") as file:
            json.dump(data, file, indent=4)

    def toggle_theme(self):
        ctk.set_appearance_mode("Light" if ctk.get_appearance_mode() == "Dark" else "Dark")

    def get_game_files(self):
        game_files_dir = os.path.join(os.path.dirname(__file__), 'game_files')
        return [f.replace('.py', '') for f in os.listdir(game_files_dir) if f.endswith('.py') and f != '__init__.py']

    def on_game_file_selected(self, selected_file):
        global udp_thread
        print(f"Selected game file: {selected_file}")
        with glob_data.lock:
            glob_data.game_info = {"game_file": selected_file} # Store the game file name in glob_data

        game_file = importlib.import_module((f'game_files.{selected_file}')) # Import the game file
        load_telemetry_options(game_file) # load the telemetry options to glob_data
        # Update all telemetry dropdowns
        for effect in self.effects.values():
            print(f"Updating telemetry dropdowns for effect: {effect.effect_id}")
            telemetry_inputs = list(glob_data.game_info.get('telemetry_options', {}).keys())
            for telemetry_input in effect.telemetry_inputs: # For every telemetry input dropdown in the effect
                telemetry_input.configure(values=telemetry_inputs)

        # If there is a telemetry and effect processing thread running, try to stop it
        if udp_thread and udp_thread.is_alive(): 
            print("Stopping the previous UDP thread")
            with glob_data.lock:
                glob_data.game_info["stop_thread"] = True #this will be read within the thread to end it
            udp_thread.join(timeout=5)  # Wait for the thread to finish with a timeout of 5 seconds
            if udp_thread.is_alive():
                print("Error: Was not able to stop previous UDP Thread.")
        else:
            glob_data.game_info["stop_thread"] = False

        # Start the telemetry and effect processing thread
        udp_thread = threading.Thread(target=processing.effects_processing, args=(self, glob_data, game_file), daemon=True)
        udp_thread.start() # Start the thread

    def on_audio_device_selected(self, selected_device_value):
        global stream
        print(f"Selected audio device: {selected_device_value}")
        device_id = self.audio_device_map.get(selected_device_value) # Get the audio device_id
        
        # Create numbered outputs for each channel
        device_info = self.audio_devices[device_id] 
        num_channels = device_info['max_output_channels']
        with glob_data.lock:
            glob_data.channels = {f"channel_{i+1}": None for i in range(num_channels)}
        print(f"Created channels: {glob_data.channels}")
        print(f"channel Names: {list(glob_data.channels.keys())}")

        for effect in self.effects.values():
            effect.channel_dropdown.configure(values=list(glob_data.channels.keys()))

        # Start the audio stream
        if device_id is not None:
            if 'stream' in globals(): #check if there is a global variable named stream
                try: # Try to stop the stream if it exists - not sure if this will handle issues well, could maybe improve in future
                    stream.stop()
                    stream.close()
                except Exception as e:
                    print(f"Error stopping audio stream: {e}")
            try:
                buffer_size = int(self.buffer_size_var.get())
                stream = audio.start_audio_stream(self, device_id, buffer_size)
            except Exception as e:
                print(f"Error starting audio stream: {e}")
        else:
            print("Device ID not found")

    def on_buffer_size_selected(self, selected_buffer_size):
        print(f"Selected buffer size: {selected_buffer_size}")
        if self.selected_audio_device.get():
            self.on_audio_device_selected(self.selected_audio_device.get()) # Restart the audio stream with the new buffer size

    # recording toggle function
    def toggle_recording(self):
        glob_data.recording = not glob_data.recording   
        if glob_data.recording:
            self.record_button.configure(fg_color="red", text="Stop")
        else:
            self.record_button.configure(fg_color="grey", text="Rec")
            audio.save_recording()
            glob_data.recorded_frames = []  # Clear recorded frames after saving

    def toggle_plots(self):
        self.plotting = not self.plotting
        if self.plotting:
            self.plot_button.configure(fg_color="green", text="Stop Plots")
            self.update_plots()  # Start updating plots
        else:
            self.plot_button.configure(fg_color="grey", text="Start Plots")

    def update_plots(self):
        if self.plotting:
            for effect in self.effects.values():
                effect.plot_telemetry()
            self.after(50, self.update_plots)  # Schedule the next update in 0.1 seconds


class EffectFrame(ctk.CTkFrame):
    def __init__(self, parent, effect_id, remove_callback, effect_type="range_effect"):
        super().__init__(parent, border_width=2)

        self.effect_id = effect_id
        self.remove_callback = remove_callback
        self.effect_type = effect_type

        # Header
        self.header = ctk.CTkFrame(self)
        self.header.pack(fill="x")

        self.toggle_button = ctk.CTkButton(self.header, text="▼", width=20, command=self.toggle_collapse)
        self.toggle_button.pack(side="left", padx=5)

        self.title_entry = ctk.CTkEntry(self.header, placeholder_text="Effect Title")
        self.title_entry.pack(side="left", fill="x", expand=True, padx=5)
        
        self.remove_button = ctk.CTkButton(self.header, text="X", fg_color="red", width=20, command=self.remove_effect)
        self.remove_button.pack(side="right", padx=5)

        self.enable_var = ctk.BooleanVar(value=True)
        self.enable_checkbox = ctk.CTkCheckBox(self.header, variable=self.enable_var, text="Enabled", width=10)
        self.enable_checkbox.pack(side="right", padx=5)
        
        # Max Output Amplitude Slider
        max_output_label = ctk.CTkLabel(self.header, text="Max Output:")
        max_output_label.pack(side="left", padx=5)
        self.max_output_amplitude_var = ctk.DoubleVar(value=0.5)  # Set default value to 0.5
        self.max_output_amplitude_slider = ctk.CTkSlider(self.header, from_=0, to=1, variable=self.max_output_amplitude_var)
        self.max_output_amplitude_slider.pack(side="left", padx=5)
        self.max_output_amplitude_var.trace_add("write", lambda *args: self.max_output_value_label.configure(text=f"{self.max_output_amplitude_var.get():.2f}")) # Update the label when the slider is moved
        
        # Add a label to show the value of the max output amplitude slider
        self.max_output_value_label = ctk.CTkLabel(self.header, text=f"{self.max_output_amplitude_var.get():.2f}")
        self.max_output_value_label.pack(side="left", padx=5)
        
        # Collapsible Section
        self.content_frame = ctk.CTkFrame(self)
        self.content_frame.pack(fill="x", padx=5, pady=5)

        self.telemetry_inputs = []  # Initialize telemetry_inputs
    
        self.plot_data = deque(maxlen=1000)  # Set a max length if needed    # Initialize plot data for effect
        self.max_plotted = float('-inf')
        self.min_plotted = float('inf')

        self.create_effect_settings()

        self.collapsed = False

    def create_effect_settings(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        # Main frame for left/right sections
        self.settings_frame = ctk.CTkFrame(self.content_frame)
        self.settings_frame.pack(fill="x", padx=5, pady=5)

        in_out_label_width = 110 # One place to contoll all the label widths for the input and output settings frames

        # Left: Input settings
        self.input_frame = ctk.CTkFrame(self.settings_frame)
        self.input_frame.pack(side="left", fill="both", expand=True, padx=5)

        # Right: Output plot frame
        self.response_curve_frame = ctk.CTkFrame(self.settings_frame, height=100) 
        self.response_curve_frame.pack(side="right", fill="both", expand=True, padx=5)

        # Right: Output settings
        self.output_frame = ctk.CTkFrame(self.settings_frame)
        self.output_frame.pack(side="right", fill="both", expand=True, padx=5)

        # Process Method (Left - Input)
        self.process_method_frame = ctk.CTkFrame(self.input_frame)
        self.process_method_frame.pack(fill="x", pady=2)
        process_method_label = ctk.CTkLabel(self.process_method_frame, text="Process Method:", width = in_out_label_width)
        process_method_label.pack(side="left", padx=2, pady=0)
        self.process_method_dropdown = ctk.CTkComboBox(self.process_method_frame, values=telemetry_process_options[self.effect_type])
        self.process_method_dropdown.pack(fill="x", pady=2)
        
        # Frequency (Right - Output)
        self.frequency_frame = ctk.CTkFrame(self.output_frame)
        self.frequency_frame.pack(fill="x", pady=2)
        frequency_label = ctk.CTkLabel(self.frequency_frame, text="Frequency:", width = in_out_label_width)
        frequency_label.pack(side="left", padx=2, pady=0)
        self.frequency_entry = ctk.CTkEntry(self.frequency_frame, placeholder_text="Frequency")
        self.frequency_entry.pack(fill="x", pady=2)
        
        if self.effect_type == "range_effect":
            # Min Input (Left - Input)
            self.min_input_frame = ctk.CTkFrame(self.input_frame)
            self.min_input_frame.pack(fill="x", pady=2)
            min_input_label = ctk.CTkLabel(self.min_input_frame, text="Min Input:", width = in_out_label_width)
            min_input_label.pack(side="left", padx=2, pady=0)
            self.min_input_entry = ctk.CTkEntry(self.min_input_frame, placeholder_text="Min Input")
            self.min_input_entry.pack(fill="x", pady=2)
            
            # Min Amplitude (Right - Output)
            self.min_amplitude_frame = ctk.CTkFrame(self.output_frame)
            self.min_amplitude_frame.pack(fill="x", pady=2)
            min_amplitude_label = ctk.CTkLabel(self.min_amplitude_frame, text="Min Output:", width = in_out_label_width)
            min_amplitude_label.pack(side="left", padx=2, pady=0)
            self.min_amplitude_entry = ctk.CTkEntry(self.min_amplitude_frame, placeholder_text="Min Amplitude")
            self.min_amplitude_entry.pack(fill="x", pady=2)
            
            # Max Input (Left - Input)
            self.max_input_frame = ctk.CTkFrame(self.input_frame)
            self.max_input_frame.pack(fill="x", pady=2)
            max_input_label = ctk.CTkLabel(self.max_input_frame, text="Max Input:", width = in_out_label_width)
            max_input_label.pack(side="left", padx=2, pady=0)
            self.max_input_entry = ctk.CTkEntry(self.max_input_frame, placeholder_text="Max Input")
            self.max_input_entry.pack(fill="x", pady=2)
            

             # Output Exponent (Right - Output)
            self.output_expo_frame = ctk.CTkFrame(self.output_frame)
            self.output_expo_frame.pack(fill="x", pady=2)
            output_expo_label = ctk.CTkLabel(self.output_expo_frame, text="Output Exponent:", width = in_out_label_width)
            output_expo_label.pack(side="left", padx=2, pady=0)
            self.plot_response_button = ctk.CTkButton(self.output_expo_frame, text="Plot", command=self.plot_response_curve, width=50)
            self.plot_response_button.pack(side="right", padx=2)
            self.output_expo = ctk.CTkEntry(self.output_expo_frame, placeholder_text="Output Exponent")
            self.output_expo.pack(fill="x", pady=2)
            self.output_expo.insert(0, str(1))  # Default value
            self.output_expo.bind("<Return>", lambda e: self.plot_response_curve())
            self.output_expo.bind("<FocusOut>", lambda e: self.plot_response_curve())

            # Channel Selection (Right - Output)
            self.channel_frame = ctk.CTkFrame(self.output_frame)
            self.channel_frame.pack(fill="x", pady=2)
            channel_label = ctk.CTkLabel(self.channel_frame, text="Channel:", width = in_out_label_width)
            channel_label.pack(side="left", padx=2, pady=0)
            self.channel_dropdown = ctk.CTkComboBox(self.channel_frame, variable=ctk.StringVar(), values=list(glob_data.channels.keys()))
            self.channel_dropdown.pack(fill="x", pady=0)
            
        elif self.effect_type == "trigger_effect":
            # Pulse Duration (Right - Output)
            self.pulse_duration_frame = ctk.CTkFrame(self.output_frame)
            self.pulse_duration_frame.pack(fill="x", pady=2)
            pulse_duration_label = ctk.CTkLabel(self.pulse_duration_frame, text="Pulse Duration:", width = in_out_label_width)
            pulse_duration_label.pack(side="left", padx=2, pady=0)
            self.pulse_duration_entry = ctk.CTkEntry(self.pulse_duration_frame, placeholder_text="Pulse Duration")
            self.pulse_duration_entry.pack(fill="x", pady=2)
            
            # Channel Selection (Right - Output)
            self.channel_frame = ctk.CTkFrame(self.output_frame)
            self.channel_frame.pack(fill="x", pady=2)
            channel_label = ctk.CTkLabel(self.channel_frame, text="Channel:", width = in_out_label_width)
            channel_label.pack(side="left", padx=2, pady=0)
            self.channel_dropdown = ctk.CTkComboBox(self.channel_frame, variable=ctk.StringVar(), values=list(glob_data.channels.keys()))
            self.channel_dropdown.pack(fill="x", pady=0)
            
        # Telemetry Inputs (Left)
        self.add_telemetry_button = ctk.CTkButton(self.input_frame, text="Add Telemetry", command=self.add_telemetry_input)
        self.add_telemetry_button.pack(pady=2)

        self.plot_frame = ctk.CTkFrame(self.content_frame)  # Frame to hold the plot
        self.plot_frame.pack(fill="both", expand=True, padx=5, pady=5)
        print("updating effect plot with self")


    def plot_response_curve(self):
        def calculate_amplitude(input_value):
            return processing.amplitude_calc(self, input_value)

        # Get min/max values
        min_input = float(self.min_input_entry.get())
        max_input = float(self.max_input_entry.get())
        min_amp = float(self.min_amplitude_entry.get())
        max_amp = float(self.max_output_amplitude_slider.get())

        # Define input range with higher resolution
        input_range = np.linspace(min_input, max_input, 100)
        amplitudes = [calculate_amplitude(i) for i in input_range]

        # Get canvas size
        width = self.response_curve_frame.winfo_width()
        height = self.response_curve_frame.winfo_height()
        print(f"Canvas size: {width}x{height}")
        
        # Define margins
        margin_x = 40
        margin_y = 20
        plot_width = (width - 2 * margin_x)
        plot_height = height - 2 * margin_y

        print(f"Plot size: {plot_width}x{plot_height}")

        # Check if canvas already exists
        if not hasattr(self, "response_canvas"):
            print("Creating new canvas")
            self.response_canvas = tk.Canvas(self.response_curve_frame, bg='#3a3a3a', highlightthickness=0)
            self.response_canvas.config()
            self.response_canvas.pack(fill='both', expand=True)
        else:
            self.response_canvas.delete("all")  # Clear previous drawings
        
        # Transform function values to fit canvas coordinates
        def transform_x(value):
            return margin_x + (value - min_input) / (max_input - min_input) * plot_width
        def transform_y(value):
            return height - margin_y - (value - min_amp) / (max_amp - min_amp) * plot_height
        
        # Draw axes
        self.response_canvas.create_line(margin_x, margin_y, margin_x, height - margin_y, fill='white')  # Y-axis
        self.response_canvas.create_line(margin_x, height - margin_y, width - margin_x, height - margin_y, fill='white')  # X-axis
        
        # Draw plot line
        points = []
        for i in range(len(input_range)):
            x = transform_x(input_range[i])
            y = transform_y(amplitudes[i])
            points.extend((x, y))
        self.response_canvas.create_line(points, fill='orange', width=2)

        # Add labels
        self.response_canvas.create_text(width / 2, height - margin_y + 15, text="Input", fill='white', font=('Arial', 12))
        self.response_canvas.create_text(margin_x - 15, height / 2, text="Output", fill='white', font=('Arial', 12), angle=90)


    def change_effect_type(self, new_type):
        self.effect_type = new_type
        self.create_effect_settings()

    def toggle_collapse(self):
        self.collapsed = not self.collapsed
        self.content_frame.pack_forget() if self.collapsed else self.content_frame.pack(fill="x", padx=5, pady=5)
        self.toggle_button.configure(text="►" if self.collapsed else "▼")

    def add_telemetry_input(self):
        telemetry_frame = ctk.CTkFrame(self.input_frame)
        telemetry_frame.pack(fill="x", pady=2)

        telemetry_dropdown = ctk.CTkComboBox(telemetry_frame, variable=ctk.StringVar(), values=list(glob_data.game_info.get('telemetry_options', {}).keys()))        
        telemetry_dropdown.pack(side="left", fill="x", expand=True, padx=2)

        remove_btn = ctk.CTkButton(telemetry_frame, text="X", fg_color="red", width=20, command=lambda: self.remove_telemetry_input(telemetry_frame, telemetry_dropdown))
        remove_btn.pack(side="right", padx=2)

        # Store the dropdown widget in the list
        self.telemetry_inputs.append(telemetry_dropdown)

    def remove_telemetry_input(self, frame, dropdown):
        frame.destroy()
        self.telemetry_inputs.remove(dropdown)

    def remove_effect(self):
        self.destroy()
        self.remove_callback(self.effect_id)

    def plot_telemetry(self):
        # Initialize the plot canvas if it doesn't exist
        if not hasattr(self, "plot_canvas"):
            self.plot_canvas = tk.Canvas(self.plot_frame, height=150, bg="#3a3a3a", highlightthickness=0)
            self.plot_canvas.pack(fill="both", expand=True)
            print("Initialized plot canvas")
        try:
            if hasattr(self, "plot_canvas"):
                if self.plot_canvas.find_all():
                    self.plot_canvas.delete("all")
            else:
                print("Plot canvas not initialized")
                return
        except Exception as e:
            print(f"Error deleting canvas items: {e}")
            if hasattr(self, "plot_canvas"): # Reinitialize the canvas if it caused an error
                self.plot_canvas.destroy()
            self.plot_canvas = tk.Canvas(self.plot_frame, height=150, bg="#3a3a3a", highlightthickness=0)
            self.plot_canvas.pack(fill="both", expand=True)
        
        if self.plot_data and max(self.plot_data) > self.max_plotted:
            self.max_plotted = max(self.plot_data)
        if self.plot_data and min(self.plot_data) < self.min_plotted:
            self.min_plotted = min(self.plot_data)
        if self.plot_data:
            self.draw_plot(self.plot_data)


    def draw_plot(self, plot_data):
        # Get current width and height of the plot canvas
        width = self.plot_canvas.winfo_width()
        height = self.plot_canvas.winfo_height()
        padding = 10  # Maintain constant padding

        # Ensure we don't get a division by zero error
        min_val, max_val = self.min_plotted, self.max_plotted
        range_val = max_val - min_val if max_val - min_val != 0 else 1
        
        # Scale the data based on the current canvas size
        scaled_data = [((val - min_val) / range_val) * (height - 2 * padding) for val in plot_data]
        
        # Calculate step size based on number of data points and available width
        step_x = (width - 2 * padding) / max(len(scaled_data) - 1, 1)
        
        # Calculate points
        points = [(padding + i * step_x, height - padding - y) for i, y in enumerate(scaled_data)]
        
        # Clear the canvas before drawing (optional to prevent layering old plots)
        self.plot_canvas.delete("all")
        
        n = 1  # Plot every nth point (you can adjust this if needed)
        for i in range(n, len(points), n):
            self.plot_canvas.create_line(points[i - n], points[i], fill="orange", width=3)
        
        # Display the max value at the top left with a larger font
        self.plot_canvas.create_text(padding, padding, anchor="nw", text=f"max: {max_val:.2f}", fill="orange", font=("Roboto", 18))

    def get_data(self):
        data = {
            "effect_title": self.title_entry.get(),
            "effect_type": self.effect_type,
            "effect_enabled": self.enable_var.get(),
            "channel": self.channel_dropdown.get(),
            "telemetry_inputs": [{"field_name": telemetry.get(), "packet_id": glob_data.game_info['telemetry_options'].get(telemetry.get())} for telemetry in self.telemetry_inputs],
            "max_output_amplitude": self.max_output_amplitude_slider.get()
        }

        if self.effect_type == "range_effect":
            data.update({
                "process_method": self.process_method_dropdown.get(),
                "frequency": float(self.frequency_entry.get() or 0),
                "min_output_amplitude": float(self.min_amplitude_entry.get() or 0),
                "output_expo": float(self.output_expo.get() or 1),
                "min_input": float(self.min_input_entry.get() or 0),
                "max_input": float(self.max_input_entry.get() or 0)
            })
        elif self.effect_type == "trigger_effect":
            data.update({
                "process_method": self.process_method_dropdown.get(),
                "frequency": float(self.frequency_entry.get() or 0),
                "pulse_duration": float(self.pulse_duration_entry.get() or 0)
            })

        return data

    def load_data(self, data):
        self.title_entry.delete(0, tk.END); self.title_entry.insert(0, data.get("effect_title", ""))
        self.change_effect_type(data.get("effect_type", "range_effect"))
        self.enable_var.set(data.get("effect_enabled", True))
        self.toggle_collapse()
        self.max_output_amplitude_slider.set(data.get("max_output_amplitude", 0.5))

        if self.effect_type == "range_effect":
            self.process_method_dropdown.set(data.get("process_method", "max"))
            self.frequency_entry.delete(0, tk.END); self.frequency_entry.insert(0, str(data.get("frequency", 0)))
            self.min_amplitude_entry.delete(0, tk.END); self.min_amplitude_entry.insert(0, str(data.get("min_output_amplitude", 0)))
            self.output_expo.delete(0, tk.END); self.output_expo.insert(0, str(data.get("output_expo", 1)))
            self.min_input_entry.delete(0, tk.END); self.min_input_entry.insert(0, str(data.get("min_input", 0)))
            self.max_input_entry.delete(0, tk.END); self.max_input_entry.insert(0, str(data.get("max_input", 0)))
            self.channel_dropdown.set(data.get("channel", "channel_1"))
        elif self.effect_type == "trigger_effect":
            self.process_method_dropdown.set(data.get("process_method", "change"))
            self.frequency_entry.delete(0, tk.END); self.frequency_entry.insert(0, str(data.get("frequency", 0)))
            self.pulse_duration_entry.delete(0, tk.END); self.pulse_duration_entry.insert(0, str(data.get("pulse_duration", 0)))
            self.channel_dropdown.set(data.get("channel", "channel_1"))

        for telemetry in data.get("telemetry_inputs", []):
            self.add_telemetry_input() # Virtually "pressing" add telemetry button
            self.telemetry_inputs[-1].set(telemetry["field_name"])
        self.plot_telemetry()
        
