python -m pip install --upgrade pip

pip install opencv-python==4.13.0.92 mediapipe==0.10.35 pygame-ce

pip install pyinstaller

cd /d "%~dp0"
pyinstaller --onefile --noconsole --add-data "face_landmarker.task;." --add-data "hand_landmarker.task;." --add-data "games;games" main.py