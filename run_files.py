import sys
import subprocess

procs = []
s1 = subprocess.Popen([sys.executable, 'server.py', 'Alford'])
procs.append(s1)
s2 = subprocess.Popen([sys.executable, 'server.py', 'Ball'])
procs.append(s2)
s3 = subprocess.Popen([sys.executable, 'server.py', 'Hamilton'])
procs.append(s3)
s4 = subprocess.Popen([sys.executable, 'server.py', 'Holiday'])
procs.append(s4)
s5 = subprocess.Popen([sys.executable, 'server.py', 'Welsh'])
procs.append(s5)

for proc in procs:
    proc.wait()
