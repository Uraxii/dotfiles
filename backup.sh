#!/bin/bash

declare -a dot_targets=(
	"hypr"
	"nvim"
	"tofi"
	"rofi"
)

for trg in ${dot_targets[@]}; do
	path="$HOME/.config/${trg}"
	cp -r $path ./.config
done
