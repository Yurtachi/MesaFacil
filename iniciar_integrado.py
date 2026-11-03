"""Servidor + simuladores para as mesas 02..N; a mesa 01 fica livre para o ESP32 virtual do Velxio."""
import runpy
import sys

sys.argv.append('--sem-mesa-01')
runpy.run_module('iniciar', run_name='__main__')
