## CapsuleAPI

Python code must load:
`CapsuleAPI/bin/CapsuleClient.dll`

# How to run: Mock mode (no hardware)
python src/main.py --mode mock --duration 60

# How to run: Real device (auto-discover)
python src/main.py --mode real

# How to run: Specific device, custom output, skip plots
python src/main.py --mode real --device AA:BB:CC:DD:EE:FF --output /tmp/eeg --no-plots

# How to run: Tests
pytest