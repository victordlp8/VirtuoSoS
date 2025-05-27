import mido
import configparser
import time
import argparse
import logging
import signal
import sys
from instruments import Empads
from modules import play

CONFIG_FILE = 'config.ini'

# Global variables for cleanup
instruments = []
outport = None
running = True

def setup_logging(debug_mode=False):
    """Setup logging system with VirtuoSoS logger"""
    logger = logging.getLogger('VirtuoSoS')
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    
    if debug_mode:
        formatter = logging.Formatter('[%(asctime)s] [%(name)s] [%(levelname)s] - %(message)s')
    else:
        formatter = logging.Formatter('[%(name)s] - [%(levelname)s] - %(message)s')
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

def get_device_names(device_type='input'):
    if device_type == 'input':
        return mido.get_input_names()
    elif device_type == 'output':
        return mido.get_output_names()
    return []

def update_config_device_name(section, option, value):
    logger = logging.getLogger('VirtuoSoS')
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    if not config.has_section(section):
        config.add_section(section)
    config.set(section, option, value)
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
    logger.info(f"Updated {option} to: {value}")

def load_instruments(config, debug_mode=False):
    """Load and initialize instrument processors"""
    logger = logging.getLogger('VirtuoSoS')
    instruments = []
    
    logger.info("Loading instruments:")
    
    # Load each instrument using their own load_from_config method
    empads = Empads.load_from_config(config, debug_mode)
    if empads:
        instruments.append(empads)
    
    wavemin = Wavemin.load_from_config(config, debug_mode)
    if wavemin:
        instruments.append(wavemin)
    
    return instruments

def show_available_devices():
    """Display all available MIDI devices"""
    logger = logging.getLogger('VirtuoSoS')
    logger.info("\n=== Available MIDI Devices ===")
    
    logger.info("\nInput devices:")
    inputs = get_device_names('input')
    if inputs:
        for i, name in enumerate(inputs):
            logger.info(f"  {i}: {name}")
    else:
        logger.info("  No input devices found")
    
    logger.info("\nOutput devices:")
    outputs = get_device_names('output')
    if outputs:
        for i, name in enumerate(outputs):
            logger.info(f"  {i}: {name}")
    else:
        logger.info("  No output devices found")
    logger.info("=" * 30)

def main_menu(debug_mode=False):
    logger = logging.getLogger('VirtuoSoS')
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)

    if not config.has_section('MIDI'):
        config.add_section('MIDI')
    if not config.has_option('MIDI', 'input_device'):
        config.set('MIDI', 'input_device', 'Please set input device')
    if not config.has_option('MIDI', 'output_device'):
        config.set('MIDI', 'output_device', 'Please set output device')
    
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
    
    input_device_name = config.get('MIDI', 'input_device', fallback='Not Set')
    output_device_name = config.get('MIDI', 'output_device', fallback='Not Set')

    while True:
        print("\n--- MIDI Configuration Menu ---")
        if debug_mode:
            print("(DEBUG MODE ENABLED)")
        print(f"1. Modify Input MIDI Device (current: {input_device_name})")
        print(f"2. Modify Output MIDI Device (current: {output_device_name})")
        print("3. Run VirtuoSoS input relayer script with current settings")
        print("4. Play a MIDI file")
        print("5. Show available MIDI devices")
        print("6. Exit")

        choice = input("Enter your choice (1-6): ")

        if choice == '1':
            print("\nAvailable MIDI Input Devices:")
            available_inputs = get_device_names('input')
            if not available_inputs:
                print("No MIDI input devices found.")
                continue
            for i, name in enumerate(available_inputs):
                print(f"  {i}: {name}")
            try:
                selection = int(input(f"Enter number for new input device (0-{len(available_inputs)-1}): "))
                if 0 <= selection < len(available_inputs):
                    new_input_name = available_inputs[selection]
                    update_config_device_name('MIDI', 'input_device', new_input_name)
                    input_device_name = new_input_name
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input. Please enter a number.")
        
        elif choice == '2':
            print("\nAvailable MIDI Output Devices:")
            available_outputs = get_device_names('output')
            if not available_outputs:
                print("No MIDI output devices found.")
                continue
            for i, name in enumerate(available_outputs):
                print(f"  {i}: {name}")
            try:
                selection = int(input(f"Enter number for new output device (0-{len(available_outputs)-1}): "))
                if 0 <= selection < len(available_outputs):
                    new_output_name = available_outputs[selection]
                    update_config_device_name('MIDI', 'output_device', new_output_name)
                    output_device_name = new_output_name
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        elif choice == '3':
            if input_device_name == 'Not Set' or input_device_name == 'Please set input device' or \
               output_device_name == 'Not Set' or output_device_name == 'Please set output device':
                logger.error("MIDI devices not configured. Please set them first.")
                continue
            logger.info("Starting MIDI processing...")
            return input_device_name, output_device_name
        
        elif choice == '4':
            # Play MIDI file option
            if output_device_name == 'Not Set' or output_device_name == 'Please set output device':
                logger.error("Output MIDI device not configured. Please set it first (option 2).")
                continue
            
            file_path = input("\nEnter the path to the MIDI file: ").strip().strip('"\'')
            
            if not file_path:
                print("No file path provided.")
                continue
            
            logger.info(f"Playing MIDI file: {file_path}")
            logger.info(f"Output device: {output_device_name}")
            
            # Show file info before playing
            file_info = play.get_midi_file_info(file_path)
            if file_info:
                logger.info(f"File info:")
                logger.info(f"  - Duration: {file_info.get('length_seconds', 0):.2f} seconds")
                logger.info(f"  - Tracks: {file_info.get('tracks', 0)}")
                logger.info(f"  - Total messages: {file_info.get('total_messages', 0)}")
            
            # Play the MIDI file
            success = play.play_midi_file(file_path, output_device_name, debug_mode)
            if success:
                logger.info("Playback completed successfully")
            else:
                logger.error("Playback failed")
            
            input("\nPress Enter to return to menu...")
        
        elif choice == '5':
            show_available_devices()
        
        elif choice == '6':
            logger.info("Exiting.")
            return None, None
        
        else:
            print("Invalid choice. Please enter a number between 1 and 6.")

def emergency_stop():
    """Emergency stop all instruments"""
    global instruments, outport, running
    logger = logging.getLogger('VirtuoSoS')
    
    running = False
    logger.warning("Emergency stop - stopping all instruments")
    
    # Always try to send comprehensive all notes off if we have an output port
    if outport:
        try:
            logger.info("Sending emergency all notes off...")
            play.comprehensive_all_notes_off(outport, logger)
        except Exception as e:
            logger.error(f"Error during emergency all notes off: {e}")
    
    # Also try instrument-specific emergency stops if available
    if instruments and outport:
        for instrument in instruments:
            try:
                instrument.emergency_stop_all_notes(outport)
            except Exception as e:
                logger.error(f"Error during emergency stop for {instrument.name}: {e}")
    
    # If no outport is available, log that we cannot send emergency stop
    if not outport:
        logger.warning("No output port available for emergency stop")

def cleanup_and_exit():
    """Cleanup function to ensure all notes are stopped before exit"""
    logger = logging.getLogger('VirtuoSoS')
    logger.info("Performing final cleanup...")
    
    # Try emergency stop first
    try:
        emergency_stop()
    except Exception as e:
        logger.error(f"Error during emergency stop: {e}")
    
    logger.info("Cleanup completed")

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    logger = logging.getLogger('VirtuoSoS')
    logger.info("Interrupt signal received. Performing emergency stop...")
    cleanup_and_exit()
    sys.exit(0)

def main():
    global instruments, outport, running
    
    parser = argparse.ArgumentParser(description='VirtuoSoS MIDI Processor')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode with detailed logging')
    parser.add_argument('--play', type=str, help='Play a MIDI file through the output device')
    args = parser.parse_args()
    
    logger = setup_logging(args.debug)
    
    if args.debug:
        logger.debug("Debug mode enabled")
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Handle MIDI file playback mode
    if args.play:
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        
        # Get output device from config or prompt user to set it
        if not config.has_section('MIDI'):
            config.add_section('MIDI')
        
        output_device_name = config.get('MIDI', 'output_device', fallback=None)
        
        if not output_device_name or output_device_name in ['Not Set', 'Please set output device']:
            logger.error("Output MIDI device not configured.")
            logger.info("Please run the program without --play first to configure MIDI devices.")
            show_available_devices()
            return
        
        logger.info(f"Playing MIDI file: {args.play}")
        logger.info(f"Output device: {output_device_name}")
        
        # Show file info before playing
        file_info = play.get_midi_file_info(args.play)
        if file_info:
            logger.info(f"File info:")
            logger.info(f"  - Duration: {file_info.get('length_seconds', 0):.2f} seconds")
            logger.info(f"  - Tracks: {file_info.get('tracks', 0)}")
            logger.info(f"  - Total messages: {file_info.get('total_messages', 0)}")
        
        # Play the MIDI file
        success = play.play_midi_file(args.play, output_device_name, args.debug)
        if not success:
            logger.error("Playback failed")
        
        return
    
    # Original functionality for live MIDI processing
    input_device_name, output_device_name = main_menu(args.debug)

    if not input_device_name or not output_device_name:
        return

    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    instruments = load_instruments(config, args.debug)

    logger.info(f"Input: {input_device_name}")
    logger.info(f"Output: {output_device_name}")

    try:
        with mido.open_input(input_device_name) as inport, \
             mido.open_output(output_device_name) as outport_local:
            
            outport = outport_local
            
            logger.info("MIDI processor started. Press Ctrl+C to stop.")

            while running:
                try:
                    msg = inport.poll()
                    if msg:
                        # if args.debug:
                        #     logger.debug(f"Received: {msg}")
                        
                        processed = False
                        for instrument in instruments:
                            if instrument.process_message(msg, outport):
                                processed = True
                                break
                        
                        if not processed:
                            outport.send(msg)
                            # if args.debug:
                            #     logger.debug(f"Forwarded: {msg}")
                    else:
                        time.sleep(0.001)
                        
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    continue

    except KeyboardInterrupt:
        emergency_stop()

    except Exception as e:
        logger.error(f"MIDI processing error: {e}")
        logger.error(f"Input device: '{input_device_name}'")
        logger.error(f"Output device: '{output_device_name}'")
        show_available_devices()

if __name__ == "__main__":
    main()
