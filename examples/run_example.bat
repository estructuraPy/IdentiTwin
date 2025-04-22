@echo off

echo Using Conda environment...
call conda activate identitwin

echo Running Identitwin System in simulation mode...
python initialization.py --simulation
pause
