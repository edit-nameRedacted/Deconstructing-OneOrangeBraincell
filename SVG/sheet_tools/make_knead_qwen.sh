#!/bin/sh
# Qwen-Image-Edit kneading keys from the both-paws-down paw key (out/paw_keys/frame_01.png).
# L = leftmost foot in the picture (cat's right front), M = middle foot (cat's left front).
# Each edit keeps only a box around that foot; pick seeds from out/knead_qwen/*/contact.png.
set -e
PY=.venv/Scripts/python.exe; SRC=out/paw_keys/frame_01.png; SEEDS=${SEEDS:-42,7,2024,101}
BOX_L=35,230,92,392; BOX_M=88,230,135,392
NOSHADOW="Do not draw any shadow on the ground. Do not add any new leg or paw."
LIFT="slightly, so it hovers just above the ground with its toes curled under, and the other feet stay on the ground. Move that same leg. $NOSHADOW The head, face and body do not move."
PUSH="presses down into the ground with its toes spread wide apart and its claws just showing, like a cat kneading a soft blanket. That foot stays in the same place. Every other foot stays exactly as it is. $NOSHADOW The head, face and body do not move."
$PY qwen_edit.py $SRC out/knead_qwen/lift_L --seeds $SEEDS --box $BOX_L --prompt "At the bottom of the picture the cat has three feet touching the ground. Lift the leftmost of those three feet $LIFT"
$PY qwen_edit.py $SRC out/knead_qwen/push_L --seeds $SEEDS --box $BOX_L --prompt "At the bottom of the picture the cat has three feet touching the ground. Only the leftmost of those three feet $PUSH"
$PY qwen_edit.py $SRC out/knead_qwen/lift_M --seeds $SEEDS --box $BOX_M --prompt "At the bottom of the picture the cat has three feet touching the ground. Lift the middle one of those three feet $LIFT"
$PY qwen_edit.py $SRC out/knead_qwen/push_M --seeds $SEEDS --box $BOX_M --prompt "At the bottom of the picture the cat has three feet touching the ground. Only the middle one of those three feet $PUSH"
