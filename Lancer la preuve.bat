@echo off
rem Lance la preuve des pigeons : un point de couleur par session Claude, pose la ou elle travaille.
rem Pour arreter : le bouton "Arreter les pigeons" du petit panneau, sur l'ecran du bas.
cd /d "%~dp0"
start "" pythonw preuve_pigeons.py
