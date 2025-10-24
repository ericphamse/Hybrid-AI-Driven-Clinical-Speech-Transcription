[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/lcU6rT0p)

# Hybrid AI-Driven Clinical Speech Transcription in Noisy, Low-Connectivity Environments
## Made in collaboration with group PSA-2511
### The following is the installation guide made for those who are keen in trying out the project themselves.

First and foremost, since the code is a hybrid of python and c code. There are 2 ways to run the code in different devices (i.e: Windows, MacOS)

## Windows:

## Step 1:
### Before we get into it, there are certain libraries such as "pydantic" or "llama-cpp" that requires special toolchains or builds, therefore you need to download:
### 1. Rust Toolchain. https://rust-lang.org/tools/install/
### 2. VS Buildtool. https://visualstudio.microsoft.com/downloads/ -> Tools for VS
### Download requirements.txt and run the following command: pip install -r requirements.txt
### Step 2:
### After downloading all of the base code and required libraries, you need to load the project into any windows code environment, mainly ones that work with python.
### Step 3:
### This step requires you to make a folder named "model" inside of the project, like one of the folders like widgets and such. Place it at where main.py is located
### Once that's done, download vosk: https://alphacephei.com/vosk/models -> vosk-model-small-en-us-0.15.
### And Qwen 1.5B params: [https://huggingface.co/MaziyarPanahi/Qwen2.5-1.5B-Instruct-GGUF](https://huggingface.co/MaziyarPanahi/Qwen2.5-1.5B-Instruct-GGUF) -> Qwen2.5-1.5B-Instruct.Q8_0.gguf
### Above you can replace it with any other quantized model versions of Qwen 1.5B. Or even attempt to used it with more heavier, powerful models.
### After installing everything, the code should be working, simply run main.py and wait until a window pops up, indicating the "app" has been launched.

## Mac:

### 1. Install brew first and then python
### 2. ⁠active environment (code is slightly didferent for Mac)
### 3. ⁠download dependency (pip) of the libraries/module of the project 
### 4. ⁠download kivy dependancy (recommend)
### 5. ⁠download models
### 6. ⁠run with the same command as window

### All libraries used in the project respectively belong to their creators. This project started as an assignment as well as working with a real client, inside of a real world environment and professionalism.
