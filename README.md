# Whisper Translator PoC

Based on **Whisper AI** model. You can chose an input source and then all audio input is captured and processes with whisper for translation from any-to-english. A PoC UI is also available, here you can choose the source input language, the input source and the time-phrase-limit( maximum time to capture audio before processing ). In Windows we have the **WSAPI** that allows us to capture the output devices as it was an input (we can capture the audio you are already listening), this devices should have a *Loopback* word in his name. For Mac users you need to install a [loopback device](http://en.wikipedia.org/wiki/Loopback#Virtual_network_interface), try with https://radio.co/blog/loopback-audio, https://www.macupdate.com/app/mac/58464/loopback. On linux on *PulseAudio* and *ALSA* you need to properly configure this capture devices (search for Linux doc).


## How to use
Since is in Poc phase there aren't any available bundle.

We are using [poetry](https://python-poetry.org/) as venv manager to has all app dependencies isolated from your python installation

 1. You need `make` in your system ( i think that all UNIX based systems has this program )
    * Windows users should download from [make installer page](https://gnuwin32.sourceforge.net/packages/make.htm) and meke avaible in your path (meaning that you can call make from the terminal)
 2. You need `python` 3.8 or above in your system ( i think that all UNIX based systems has this program )
    * Windows users should install python from Microsoft Store or download from the [python page](https://www.python.org/downloads/)
 3. Whisper need `ffmpeg` if they are going to process a file, but we aren't using a file, all data is pass on memory so i think we don't need it. If you have any unexpected error related with this, please install `ffmpeg` in your system.
 4. Open a terminal in the root project and run `make install` or `make win-install` if you are on Windows.
 5. Run `make run` on your terminal
    * the first time whisper model need to be downloaded, you should see a progress bar on the terminal