import threading

# This is to store shared variables that need to be accesed by multiple files

# Shared state class
class globdata:
    def __init__(self):
        self.game_info = {} # Used to store some game information after loading the game file
        self.telemetry = {}  # Dictionary to store telemetry fields and corresponding packet_id
        self.audio = {} # Dictionary to store audio data between audio callbacks
        self.channels = {}  # Variable to store channels
        self.recorded_frames = []  # Variable to store recorded frames
        self.plot_telemetry = {}  # Store telemetry data for plotting
        self.lock = threading.Lock()  # Add a threading lock

# Global instance of ShakeVars
glob_data = globdata()
