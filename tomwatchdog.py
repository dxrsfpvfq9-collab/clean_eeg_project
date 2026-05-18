import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import os
#from pyvirtualdisplay import Display


class NewFileHandler(FileSystemEventHandler):
    def on_created(self, event):
        # Check if the event is a file creation event
        print("on_created is called")
        if event.is_directory:
            return None

        # Run the specified program on the new file
        print (event.src_path)
        path = event.src_path
        if path.lower().endswith('.edf'):
#        path = path.replace("\", "/")
#        path = path.replace("/", "\\")
          runstring = f'py module7.py "{path}" '
          print("run: ", runstring)

#          display =  Display(visible=0, size=(1024,768))
#          display.start()

          subprocess.Popen(["python", "module7.py", path])
 
#          subprocess.Popen(["py", runstring])
#          os.system(runstring)
#        run_program(event.src_path)

#          display.stop()

# want file path to be "c:\Users/tcollura/Dropbox/Documents/Projects/ChatGPT/python/screens/augie sharing/CleanEEGProject/"

def run_program(file_path):
    # Specify the program to run and its arguments
    program = "py module7.py"
    args = [program, "\'", file_path, "\'"]

    # Run the program using subprocess
    subprocess.run(args)


if __name__ == "__main__":

    print("entering main")

    # Specify the directory to monitor
#    monitor_dir = "c:/Users/tcollura/Dropbox/STS EEG Quality Assurance Reviews"
#    monitor_dir = "c:/app/STSEEGScreening/Source/Practitioners"
    monitor_dir = "c:/inetpub/wwwroot/EEGScreening/Source/Practitioners"

    print("monitor dir:", monitor_dir)

    # Create an event handler
    event_handler = NewFileHandler()

    # Create an observer
    observer = Observer()

    # Schedule the observer to monitor the directory
    observer.schedule(event_handler, monitor_dir, recursive=True)

    # Start the observer
    observer.start()
    print("observer created and started")

    try:
        # Run indefinitely
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # Stop the observer when interrupted
        observer.stop()

    # Wait for the observer to finish
    observer.join()