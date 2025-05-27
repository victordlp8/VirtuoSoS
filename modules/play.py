import mido
import time
import logging
import os
import threading
from typing import Optional
from tqdm import tqdm

def validate_midi_file(file_path: str) -> bool:
    """
    Validate if the file exists and is a valid MIDI file
    
    Args:
        file_path: Path to the MIDI file
        
    Returns:
        bool: True if valid, False otherwise
    """
    logger = logging.getLogger('VirtuoSoS')
    
    if not os.path.exists(file_path):
        logger.error(f"MIDI file not found: {file_path}")
        return False
    
    if not file_path.lower().endswith(('.mid', '.midi')):
        logger.error(f"File does not appear to be a MIDI file: {file_path}")
        return False
    
    try:
        # Try to open the file to validate it's a proper MIDI file
        mido.MidiFile(file_path)
        return True
    except Exception as e:
        logger.error(f"Invalid MIDI file: {e}")
        return False

def load_midi_file(file_path: str) -> Optional[mido.MidiFile]:
    """
    Load a MIDI file
    
    Args:
        file_path: Path to the MIDI file
        
    Returns:
        MidiFile object or None if failed
    """
    logger = logging.getLogger('VirtuoSoS')
    
    if not validate_midi_file(file_path):
        return None
    
    try:
        midi_file = mido.MidiFile(file_path)
        return midi_file
    except Exception as e:
        logger.error(f"Error loading MIDI file: {e}")
        return None

def play_midi_file(file_path: str, output_device_name: str, debug_mode: bool = False, fix_notes: bool = False, min_duration_ms: int = 100) -> bool:
    """
    Play a MIDI file through the specified output device
    
    Args:
        file_path: Path to the MIDI file
        output_device_name: Name of the MIDI output device
        debug_mode: Enable debug logging
        fix_notes: Whether to fix short notes by extending their duration
        min_duration_ms: Minimum note duration in milliseconds (used when fix_notes=True)
        
    Returns:
        bool: True if playback completed successfully, False otherwise
    """
    logger = logging.getLogger('VirtuoSoS')
    
    # Load the MIDI file
    midi_file = load_midi_file(file_path)
    if not midi_file:
        return False
    
    # Apply note fixing if requested
    if fix_notes:
        logger.info(f"Applying note duration fix (minimum: {min_duration_ms}ms)")
        midi_file = fix_short_notes(midi_file, min_duration_ms)
    
    # Get song duration for progress bar
    song_duration = midi_file.length
    total_seconds = int(song_duration) + 1  # Add 1 to ensure we reach 100%
    
    outport = None
    progress_bar = None
    progress_thread = None
    progress_stop_event = threading.Event()
    
    def update_progress():
        """Update progress bar every second"""
        nonlocal progress_bar
        start_time = time.time()
        
        # Get just the filename for display
        filename = os.path.basename(file_path)
        
        with tqdm(total=total_seconds, desc=f"♪ {filename}", unit="s", 
                  bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt}s [{elapsed}<{remaining}]",
                  ncols=80) as pbar:
            progress_bar = pbar
            
            while not progress_stop_event.is_set():
                elapsed = time.time() - start_time
                current_second = int(elapsed)
                
                # Update progress bar to current second
                if current_second < total_seconds and pbar.n < current_second:
                    pbar.update(current_second - pbar.n)
                
                # Check every 0.1 seconds for smooth updates
                if progress_stop_event.wait(0.1):
                    break
            
            # Complete the progress bar
            pbar.update(total_seconds - pbar.n)
    
    try:
        outport = mido.open_output(output_device_name)
        logger.info(f"Starting playback on device: {output_device_name}")
        logger.info("Press Ctrl+C to stop playback")
        
        # Start progress bar in separate thread
        progress_thread = threading.Thread(target=update_progress, daemon=True)
        progress_thread.start()
        
        start_time = time.time()
        playback_interrupted = False
        
        try:
            # Play all messages from all tracks
            for msg in midi_file.play():
                outport.send(msg)
                
                # Small sleep to prevent overwhelming the output
                time.sleep(0.001)
                
        except KeyboardInterrupt:
            logger.info("Playback interrupted by user")
            playback_interrupted = True
            # Immediately send all notes off using the same port
            logger.debug("Sending immediate all notes off...")
            comprehensive_all_notes_off(outport, logger)
        except Exception as e:
            logger.error(f"Error sending MIDI message: {e}")
            playback_interrupted = True
            # Send all notes off on error too
            logger.debug("Sending all notes off due to error...")
            comprehensive_all_notes_off(outport, logger)
        
        # Stop progress bar
        progress_stop_event.set()
        if progress_thread:
            progress_thread.join(timeout=1.0)
        
        # Send all notes off at the end if playback completed normally
        if not playback_interrupted:
            end_time = time.time()
            logger.info(f"Playback completed in {end_time - start_time:.2f} seconds")
            logger.debug("Sending final all notes off...")
            comprehensive_all_notes_off(outport, logger)
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"Error opening output device '{output_device_name}': {e}")
        return False
    finally:
        # Ensure progress bar is stopped
        progress_stop_event.set()
        if progress_thread:
            progress_thread.join(timeout=1.0)
        
        # Ensure the port is always closed
        if outport:
            try:
                outport.close()
                logger.debug("MIDI output port closed")
            except Exception as e:
                logger.error(f"Error closing output port: {e}")

def comprehensive_all_notes_off(outport, logger=None):
    """
    Comprehensive function to stop all MIDI notes and sounds
    
    Args:
        outport: MIDI output port
        logger: Optional logger instance
    """
    if logger is None:
        logger = logging.getLogger('VirtuoSoS')
    
    logger.debug("Sending comprehensive all notes off...")
    
    try:
        time.sleep(0.2)
        # Send multiple rounds to ensure all notes are stopped
        for round_num in range(3):  # Send 3 rounds for maximum reliability
            if round_num > 0:
                logger.debug(f"Sending all notes off round {round_num + 1}...")
            
            for channel in range(16):
                # First: Send All Sound Off (CC 120) - most aggressive
                all_sound_off = mido.Message('control_change', 
                                           channel=channel, 
                                           control=120, 
                                           value=0)
                outport.send(all_sound_off)
                
                # Second: Send All Notes Off (CC 123)
                all_notes_off = mido.Message('control_change', 
                                           channel=channel, 
                                           control=123, 
                                           value=0)
                outport.send(all_notes_off)
                
                # Third: Send explicit note off using note_on with velocity 0 (more effective)
                for note in range(128):
                    note_off = mido.Message('note_on', 
                                          channel=channel, 
                                          note=note, 
                                          velocity=0)
                    outport.send(note_off)

                    note_off = mido.Message('note_off', 
                                          channel=channel, 
                                          note=note, 
                                          velocity=0)
                    outport.send(note_off)
                
                # Fourth: Reset All Controllers (CC 121)
                reset_controllers = mido.Message('control_change',
                                               channel=channel,
                                               control=121,
                                               value=0)
                outport.send(reset_controllers)
                
                # Fifth: Send Sustain Pedal Off (CC 64)
                sustain_off = mido.Message('control_change',
                                         channel=channel,
                                         control=64,
                                         value=0)
                outport.send(sustain_off)
                
                # Sixth: Send Soft Pedal Off (CC 67)
                soft_pedal_off = mido.Message('control_change',
                                            channel=channel,
                                            control=67,
                                            value=0)
                outport.send(soft_pedal_off)
                
                # Seventh: Send Sostenuto Pedal Off (CC 66)
                sostenuto_off = mido.Message('control_change',
                                           channel=channel,
                                           control=66,
                                           value=0)
                outport.send(sostenuto_off)
            
            # Small delay between rounds
            time.sleep(0.05)
        
        # Final delay to ensure all messages are processed
        time.sleep(0.2)
        logger.debug("Comprehensive all notes off completed")
        
    except Exception as e:
        logger.error(f"Error sending comprehensive all notes off: {e}")

def send_all_notes_off(outport):
    """
    Send all notes off messages on all channels to prevent hanging notes
    
    Args:
        outport: MIDI output port
    """
    logger = logging.getLogger('VirtuoSoS')
    comprehensive_all_notes_off(outport, logger)

def get_midi_file_info(file_path: str) -> dict:
    """
    Get information about a MIDI file without playing it
    
    Args:
        file_path: Path to the MIDI file
        
    Returns:
        dict: Information about the MIDI file
    """
    if not validate_midi_file(file_path):
        return {}
    
    try:
        midi_file = mido.MidiFile(file_path)
        
        info = {
            'file_path': file_path,
            'type': midi_file.type,
            'tracks': len(midi_file.tracks),
            'ticks_per_beat': midi_file.ticks_per_beat,
            'length_seconds': midi_file.length,
            'total_messages': sum(len(track) for track in midi_file.tracks)
        }
        
        # Count different message types
        message_types = {}
        for track in midi_file.tracks:
            for msg in track:
                msg_type = msg.type
                message_types[msg_type] = message_types.get(msg_type, 0) + 1
        
        info['message_types'] = message_types
        
        return info
        
    except Exception as e:
        logger = logging.getLogger('VirtuoSoS')
        logger.error(f"Error getting MIDI file info: {e}")
        return {}

def fix_short_notes(midi_file: mido.MidiFile, min_duration_ms: int) -> mido.MidiFile:
    """
    Fix short notes in a MIDI file by extending their duration to a minimum value.
    This algorithm NEVER removes or modifies existing messages.
    It only ADDS additional note_off messages when notes are too short.
    
    Args:
        midi_file: The original MIDI file
        min_duration_ms: Minimum note duration in milliseconds
        
    Returns:
        MidiFile: New MIDI file with additional note_off messages for short notes
    """
    logger = logging.getLogger('VirtuoSoS')
    
    # Convert minimum duration from milliseconds to ticks
    ticks_per_beat = midi_file.ticks_per_beat
    # Default to 120 BPM (500000 microseconds per beat)
    microseconds_per_beat = 500000
    
    # Look for tempo changes in the file
    for track in midi_file.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                microseconds_per_beat = msg.tempo
                break
    
    # Convert to ticks: (ms / 1000) * (1000000 / microseconds_per_beat) * ticks_per_beat
    min_duration_ticks = int((min_duration_ms * 1000 * ticks_per_beat) / microseconds_per_beat)
    
    logger.info(f"Adding note_off extensions for notes shorter than {min_duration_ms}ms ({min_duration_ticks} ticks)")
    
    # Create a new MIDI file with the same properties
    new_midi_file = mido.MidiFile(type=midi_file.type, ticks_per_beat=ticks_per_beat)
    
    notes_fixed = 0
    
    for track_idx, track in enumerate(midi_file.tracks):
        # Convert track to absolute time
        absolute_messages = []
        current_time = 0
        
        for msg in track:
            current_time += msg.time
            absolute_messages.append((current_time, msg.copy()))
        
        # Track active notes using a stack approach to handle overlapping notes correctly
        active_notes = {}  # (channel, note) -> list of note_on times (stack)
        additional_note_offs = []  # Additional note_off messages to add
        
        for abs_time, msg in absolute_messages:
            if msg.type == 'note_on' and msg.velocity > 0:
                # Add this note_on to the stack
                key = (msg.channel, msg.note)
                if key not in active_notes:
                    active_notes[key] = []
                active_notes[key].append(abs_time)
                
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                # Handle note_off - match with most recent note_on (LIFO)
                key = (msg.channel, msg.note)
                if key in active_notes and active_notes[key]:
                    note_on_time = active_notes[key].pop()  # Remove most recent note_on
                    note_duration = abs_time - note_on_time
                    
                    if note_duration < min_duration_ticks:
                        # This note is too short, add an additional note_off at extended time
                        extended_time = note_on_time + min_duration_ticks
                        
                        # Create additional note_off message
                        additional_note_off = mido.Message('note_off', 
                                                         channel=msg.channel, 
                                                         note=msg.note, 
                                                         velocity=0)
                        additional_note_offs.append((extended_time, additional_note_off))
                        
                        notes_fixed += 1
                        logger.debug(f"Will add extended note_off for note {msg.note} on channel {msg.channel} at time {extended_time} (duration extended from {note_duration} to {min_duration_ticks} ticks)")
                    
                    # Clean up empty lists
                    if not active_notes[key]:
                        del active_notes[key]
        
        # Handle any remaining active notes (orphaned note_on without note_off)
        for key, note_on_times in active_notes.items():
            channel, note = key
            for note_on_time in note_on_times:
                extended_time = note_on_time + min_duration_ticks
                note_off_msg = mido.Message('note_off', channel=channel, note=note, velocity=0)
                additional_note_offs.append((extended_time, note_off_msg))
                notes_fixed += 1
                logger.debug(f"Added note_off for orphaned note {note} on channel {channel}")
        
        # Combine original messages with additional note_offs
        all_messages = absolute_messages + additional_note_offs
        
        # Sort by time and convert back to relative time
        all_messages.sort(key=lambda x: x[0])
        
        new_track = mido.MidiTrack()
        last_time = 0
        
        for abs_time, msg in all_messages:
            msg.time = abs_time - last_time
            new_track.append(msg)
            last_time = abs_time
        
        new_midi_file.tracks.append(new_track)
    
    logger.info(f"Added {notes_fixed} additional note_off messages for short notes")
    return new_midi_file
