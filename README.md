[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/lcU6rT0p)

NOTE: review requirements.txt or download it and run it on your cmd prompt to download all the necessary libraries
if you're on windows: "pip install -r requirements.txt", I don't know what's for MAC
After that, you can try to download the script I made for Kivy. And then run it on any IDE that supports python. One thing to note is that you have to manually download the models which I'll put here.
Vosk: 
https://alphacephei.com/vosk/models -> vosk-model-small-en-us-0.15
TinyLlama: 
https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/tree/main -> tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
(for TinyLlama, the difference in models are not too big, and I haven't tested out the 2nd most file heavy one yet to see if it's worth adding to the testing phase)
download them, put them inside of the script's folder, then remember to change the name of the file path. since I made a folder named "model" inside and put TtinyLlama .gguf file there and renamed it to "model/medium.gguf" and for vosk, just aside the script and didn't bother to rename it to anything else.
