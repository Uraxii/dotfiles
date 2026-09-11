function tp --description 'Attach or switch to a tmux session named after the current directory'
    _tmux_go (basename $PWD)
end
