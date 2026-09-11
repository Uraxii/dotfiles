function tr --description 'Attach or switch to an existing tmux session, refusing to create one (default: main)'
    set -l name main
    if test (count $argv) -gt 0
        set name $argv[1]
    end

    set -l red ''
    set -l dim ''
    set -l bold ''
    set -l rst ''
    if isatty stderr
        set red \e'[1;31m'
        set dim \e'[2m'
        set bold \e'[1m'
        set rst \e'[0m'
    end

    if not tmux has-session 2>/dev/null
        printf '%str:%s %serror:%s tmux not running\n' $red $rst $bold $rst >&2
        printf '%str: hint: use detach to exit a session without killing it%s\n' $dim $rst >&2
        return 1
    end

    if not tmux has-session -t "=$name" 2>/dev/null
        set -l avail (tmux list-sessions -F '#S' 2>/dev/null | string join ', ')
        test -n "$avail"; or set avail '<none>'
        printf "%str:%s %serror:%s session '%s' does not exist\n" $red $rst $bold $rst $name >&2
        printf '%str: hint: available: %s%s\n' $dim $avail $rst >&2
        return 1
    end

    if set -q TMUX
        tmux switch-client -t $name
    else
        tmux attach -t $name
    end
end
