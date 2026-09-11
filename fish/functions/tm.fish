function tm --description 'Attach or switch to a tmux session (default: main)'
    set -l name main
    if test (count $argv) -gt 0
        set name $argv[1]
    end
    _tmux_go $name
end
