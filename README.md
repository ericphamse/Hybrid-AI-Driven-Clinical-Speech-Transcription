[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/lcU6rT0p)
# Hybrid AI-Driven Clinical Speech Transcription in Noisy, Low-Connectivity Environments
## Made as collaborated effort from group PSA2511
### This project aims to make an IOS app via Kivy frameworks, Because the whole file is too big, there are several things needed to be downloaded, installed and properly set up in order to run this particular code.
### NOTE: review requirements.txt or download it and run it on your cmd prompt to download all the necessary libraries
if you're on windows: "pip install -r requirements.txt", I don't know what's for MAC
After that, you can download the entire file as a zip file. And extract it then run in any IDE coding environment if deployment on MacOS is not viable. One thing to note is that you have to manually download the models which I'll put here.
Vosk: 
https://alphacephei.com/vosk/models -> vosk-model-small-en-us-0.15
Qwen-1.5B-Instruct: 
https://huggingface.co/MaziyarPanahi/Qwen2.5-1.5B-Instruct-GGUF -> <ins>Qwen2.5-1.5B-Instruct.Q8_0.gguf</ins>

To get started, when you load the project inside of the workplace's folders, make a folder named "model" <- this is where most of your downloaded models will be stored. To run the code itself, <ins>it must be ran on main.py </ins>, attempting to run other .py files will result in the app not launching or being thrown an error.

### Lastly, there are some libraries such as llama cpp, which is supposedly for c environment only, but there is a wrapper library called llama-cpp-python, but it requires one to install vs build tool from microsoft, another requirement is to install rust toolchain as well, for pydantic library. So in short. Download Vs buildtool, rust toolchain, then you're able to download all of the pip installs without any problem.
