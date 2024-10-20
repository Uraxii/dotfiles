#!/bin/bash

config_dir=$HOME/.config

declare -a targets=(
	"${config_dir}/hypr"
	"${config_dir}/nvim"
	"${config_dir}/tofi"
	"${config_dir}/rofi"
	"${HOME}/.zshrc"
)

for trg in ${targets[@]}; do
	cp -r $trg .
done
