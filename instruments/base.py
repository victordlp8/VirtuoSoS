import mido
import logging
from abc import ABC, abstractmethod

class BaseInstrument(ABC):
    def __init__(self, name, midi_channel, midi_program, output_channel=None):
        self.name = name
        self.midi_channel = midi_channel
        self.output_channel = output_channel if output_channel is not None else midi_channel
        self.midi_program = midi_program
        self.active_notes = set()
        self.is_enabled = True
        self.logger = logging.getLogger('VirtuoSoS')

    @abstractmethod
    def process_message(self, msg, outport) -> bool:
        """
        Process a MIDI message for this instrument.
        
        Args:
            msg: The MIDI message to process
            outport: The MIDI output port to send messages to
            
        Returns:
            bool: True if the message was processed by this instrument, False otherwise
        """
        return False

    def is_my_channel(self, msg):
        """Check if a MIDI message belongs to this instrument's input channel"""
        return hasattr(msg, 'channel') and msg.channel == self.midi_channel

    def forward_message(self, msg, outport):
        """Forward a MIDI message unchanged but potentially to different output channel"""
        if hasattr(msg, 'channel'):
            new_msg = msg.copy(channel=self.output_channel)
            outport.send(new_msg)
        else:
            outport.send(msg)

    def send_note_on(self, note, velocity, outport):
        """Send a note on message to output channel"""
        note_on_msg = mido.Message('note_on', channel=self.output_channel, 
                                  note=note, velocity=velocity)
        outport.send(note_on_msg)
        self.active_notes.add(note)

    def send_note_off(self, note, velocity, outport):
        """Send a note off message to output channel"""
        note_off_msg = mido.Message('note_off', channel=self.output_channel, 
                                   note=note, velocity=velocity)
        outport.send(note_off_msg)
        self.active_notes.discard(note)

    def send_control_change(self, control, value, outport):
        """Send a control change message to output channel"""
        cc_msg = mido.Message('control_change', channel=self.output_channel,
                             control=control, value=value)
        outport.send(cc_msg)

    def send_program_change(self, program, outport):
        """Send a program change message to output channel"""
        pc_msg = mido.Message('program_change', channel=self.output_channel,
                             program=program)
        outport.send(pc_msg)

    def transpose_note(self, note, semitones):
        """Transpose a note by the given number of semitones"""
        transposed = note + semitones
        return max(0, min(127, transposed))

    def modify_velocity(self, velocity, factor=1.0, offset=0):
        """Modify velocity with factor and offset"""
        new_velocity = int(velocity * factor + offset)
        return max(0, min(127, new_velocity))

    def set_output_channel(self, channel):
        """Change the output channel for this instrument"""
        self.output_channel = max(0, min(15, channel))
        self.logger.info(f"{self.name}: Output channel set to {self.output_channel}")

    def stop(self):
        """Stop all active notes and reset instrument state"""
        self.active_notes.clear()

    def stop_all_notes(self, outport):
        """Send note off for all currently active notes"""
        for note in list(self.active_notes):
            self.send_note_off(note, 64, outport)

    def enable(self):
        """Enable this instrument"""
        self.is_enabled = True

    def disable(self):
        """Disable this instrument"""
        self.is_enabled = False

    def __str__(self):
        return f"{self.name} (Input Ch: {self.midi_channel}, Output Ch: {self.output_channel}, Program: {self.midi_program})"
