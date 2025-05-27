# VirtuoSoS
Small script that reinterprets [Virtuoso](https://store.steampowered.com/app/1213710/Virtuoso)'s MIDI output for [Create: Sound of Steam](https://modrinth.com/mod/create-sound-of-steam) and some other functionalities.

# How to install

1. Clone the repository:
```bash
git clone https://github.com/victordlp8/VirtuoSoS.git
cd VirtuoSoS
```

2. Install Astral UV:
   Visit [https://docs.astral.sh/uv/getting-started/installation/](https://docs.astral.sh/uv/getting-started/installation/) for installation instructions.

3. Run the program:
```bash
uv run main.py
```

# How it works

The program acts as a MIDI bridge between Virtuoso and Create: Sound of Steam. It captures MIDI output from Virtuoso, processes and reinterprets the MIDI data to make it compatible with Create: Sound of Steam's input requirements, then forwards the modified MIDI signals to the game. This allows you to use Virtuoso's advanced MIDI capabilities while playing Create: Sound of Steam.

## MIDI File Playback

You can also use VirtuoSoS to play MIDI files directly through your configured output device. This feature is completely independent from the instrument processing system and allows you to:

- Play MIDI files directly without any processing
- Fix short notes that might cause issues with certain pipes
- View detailed information about the MIDI file before playback

### Basic Usage

#### Single command usage
```bash
uv run main.py --play "path_to_midi_file"
```

#### Through the terminal interface
```bash
uv run main.py
```

And follow the corresponding instructions.

