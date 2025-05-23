import mido
import configparser
import time
import argparse
import logging
import signal
import sys
from instruments import Empads

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
        formatter = logging.Formatter('[%(asctime)s] %(name)s - %(levelname)s - %(message)s')
    else:
        formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    
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
    
    empads_input_channel = config.getint('CHANNELS', 'empads', fallback=0)
    empads_output_channel = config.getint('OUTPUT_CHANNELS', 'empads', fallback=empads_input_channel)
    empads = Empads(name="Empads", 
                   midi_channel=empads_input_channel, 
                   midi_program=0,
                   output_channel=empads_output_channel,
                   debug_mode=debug_mode)
    instruments.append(empads)
    
    logger.info("Loaded instruments:")
    for instrument in instruments:
        logger.info(f"  - {instrument}")
    
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
        print("3. Run script with current settings")
        print("4. Show available MIDI devices")
        print("5. Exit")

        choice = input("Enter your choice (1-5): ")

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
            show_available_devices()
        
        elif choice == '5':
            logger.info("Exiting.")
            return None, None
        
        else:
            print("Invalid choice. Please enter a number between 1 and 5.")

def emergency_stop():
    """Emergency stop all instruments"""
    global instruments, outport, running
    logger = logging.getLogger('VirtuoSoS')
    
    running = False
    logger.warning("Emergency stop - stopping all instruments")
    
    if instruments and outport:
        for instrument in instruments:
            try:
                instrument.emergency_stop_all_notes(outport)
            except Exception as e:
                logger.error(f"Error during emergency stop for {instrument.name}: {e}")

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    logger = logging.getLogger('VirtuoSoS')
    logger.info("Interrupt signal received. Performing emergency stop...")
    emergency_stop()
    sys.exit(0)

def main():
    global instruments, outport, running
    
    parser = argparse.ArgumentParser(description='VirtuoSoS MIDI Processor')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode with detailed logging')
    args = parser.parse_args()
    
    logger = setup_logging(args.debug)
    
    if args.debug:
        logger.info("Debug mode enabled")
    
    signal.signal(signal.SIGINT, signal_handler)
    
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
                        if args.debug:
                            logger.debug(f"Received: {msg}")
                        
                        processed = False
                        for instrument in instruments:
                            if instrument.process_message(msg, outport):
                                processed = True
                                break
                        
                        if not processed:
                            outport.send(msg)
                            if args.debug:
                                logger.debug(f"Forwarded: {msg}")
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
