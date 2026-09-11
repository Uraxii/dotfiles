function _tmux_go --description 'Attach to a tmux session, creating it detached first if missing'
    set -l name $argv[1]
    # Always ensure the session exists detached first. Splitting create from
    # attach avoids the nest-refusal that `tmux new -A` triggers from inside.
    if not tmux has-session -t $name 2>/dev/null
        tmux new-session -d -s $name
    end
    if set -q TMUX
        tmux switch-client -t $name
    else
        tmux attach -t $name
    end
end
