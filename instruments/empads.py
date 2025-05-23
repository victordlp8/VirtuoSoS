from .base import BaseInstrument
import mido
import time
import threading
import logging

class Empads(BaseInstrument):
    def __init__(self, name, midi_channel, midi_program, output_channel=None, note_off_delay=0.1, debug_mode=False):
        super().__init__(name, midi_channel, midi_program, output_channel)
        self.note_off_delay = note_off_delay
        self.debug_mode = debug_mode
        self.logger = logging.getLogger('VirtuoSoS')
        self.active_notes = set()
        self.pending_timers = {}
        self.recent_notes = set()
        self.notes_sent_off = set()  # Track notes that already had note off sent
        self.lock = threading.Lock()

    def process_message(self, msg, outport):
        """Process MIDI message and add automatic note off"""
        if not self.is_enabled or not self.is_my_channel(msg):
            return False
            
        if msg.type == 'note_on' and msg.velocity > 0:
            with self.lock:
                # Cancel any existing timer for this note
                if msg.note in self.pending_timers:
                    self.pending_timers[msg.note].cancel()
                    del self.pending_timers[msg.note]
                
                # Reset note off tracking for this note
                self.notes_sent_off.discard(msg.note)
                self.recent_notes.add(msg.note)
                
                # Send note on
                self.send_note_on(msg.note, msg.velocity, outport)
                
                # Schedule automatic note off
                timer = threading.Timer(self.note_off_delay, self._send_auto_note_off, args=[msg.note, outport])
                self.pending_timers[msg.note] = timer
                timer.start()
            
            return True
        
        elif msg.type == 'note_on' and msg.velocity == 0:
            # Ignore note off disguised as note_on with velocity 0
            if self.debug_mode:
                self.logger.debug(f"{self.name}: Ignoring incoming note off (note_on vel=0) for note {msg.note}")
            return True
            
        elif msg.type == 'note_off':
            # Ignore explicit note off
            if self.debug_mode:
                self.logger.debug(f"{self.name}: Ignoring incoming note off for note {msg.note}")
            return True
            
        elif msg.type in ['control_change', 'program_change', 'pitchwheel']:
            self.forward_message(msg, outport)
            return True
            
        return False

    def _handle_note_off(self, note, outport):
        """Handle note off - ensure only one note off is sent per note"""
        # Cancel any pending timer for this note
        if note in self.pending_timers:
            self.pending_timers[note].cancel()
            del self.pending_timers[note]
        
        # Only send note off if we haven't already sent one for this note
        if note not in self.notes_sent_off and note in self.active_notes:
            self.send_note_off_as_note_on(note, outport)
            self.notes_sent_off.add(note)
            if self.debug_mode:
                self.logger.debug(f"{self.name}: Note off {note}")

    def _send_auto_note_off(self, note, outport):
        """Send automatic note off after delay - only if not already sent"""
        with self.lock:
            # Clean up timer reference
            if note in self.pending_timers:
                del self.pending_timers[note]
            
            # Only send if note is still active and we haven't sent note off yet
            if note in self.active_notes and note not in self.notes_sent_off:
                self.send_note_off_as_note_on(note, outport)
                self.notes_sent_off.add(note)
                self.logger.debug(f"{self.name}: Auto note off {note}")

    def send_note_off_as_note_on(self, note, outport):
        """Send note off as note_on with velocity 0"""
        try:
            note_off_msg = self.create_midi_message('note_on', channel=self.output_channel, 
                                                   note=note, velocity=0)
            outport.send(note_off_msg)
            self.active_notes.discard(note)
        except Exception as e:
            self.logger.error(f"{self.name}: Error sending note off for note {note}: {e}")

    def create_midi_message(self, msg_type, **kwargs):
        """Create MIDI message"""
        return mido.Message(msg_type, **kwargs)

    def play(self, note, velocity=127):
        """Manual play method"""
        pass

    def set_note_off_delay(self, delay):
        """Set the delay before auto note-off"""
        self.note_off_delay = max(0.05, delay)
        self.logger.info(f"{self.name}: Note off delay set to {self.note_off_delay}s")

    def stop(self):
        """Stop all active notes and cancel timers"""
        with self.lock:
            for note, timer in list(self.pending_timers.items()):
                timer.cancel()
            self.pending_timers.clear()
            self.active_notes.clear()
            self.recent_notes.clear()
            self.notes_sent_off.clear()

    def emergency_stop_all_notes(self, outport):
        """Emergency stop - send note off for all notes"""
        with self.lock:
            self.logger.warning(f"{self.name}: Emergency stop")
            
            # Cancel all timers
            for note, timer in list(self.pending_timers.items()):
                timer.cancel()
            self.pending_timers.clear()
            
            # Send note off for all active notes that haven't had note off sent
            notes_to_stop = []
            for note in self.active_notes:
                if note not in self.notes_sent_off:
                    notes_to_stop.append(note)
            
            # Also include recent notes as fallback
            for note in self.recent_notes:
                if note not in self.notes_sent_off and note not in notes_to_stop:
                    notes_to_stop.append(note)
            
            # If still no notes, use drum range as last resort
            if not notes_to_stop:
                notes_to_stop = list(range(36, 82))
            
            for note in notes_to_stop:
                try:
                    self.send_note_off_as_note_on(note, outport)
                except Exception as e:
                    self.logger.error(f"Emergency stop error for note {note}: {e}")
            
            # Send All Notes Off (CC 123)
            try:
                import mido
                all_notes_off_msg = mido.Message('control_change', 
                                               channel=self.output_channel,
                                               control=123, 
                                               value=0)
                outport.send(all_notes_off_msg)
            except Exception as e:
                self.logger.error(f"Error sending All Notes Off: {e}")
            
            self.active_notes.clear()
            self.recent_notes.clear()
            self.notes_sent_off.clear()

