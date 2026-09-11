function pass_secret --description 'One field of one Proton Pass item. Logs in when the session has expired. Caches nothing, writes nothing to disk.'
    set -l item $argv[1]
    set -l field $argv[2]
    set -l reason 'interactive shell request'
    if test (count $argv) -ge 3
        set reason $argv[3]
    end

    if not type -q pass-cli
        echo 'pass_secret: pass-cli is not installed' >&2
        return 1
    end

    set -q PASS_VAULT_NAME; or set -l PASS_VAULT_NAME MachineSecrets
    set -q PASS_PAT_KEYRING_ACCOUNT; or set -l PASS_PAT_KEYRING_ACCOUNT machinesecrets-pat
    set -q PROTON_PASS_SESSION_DIR; or set -l PROTON_PASS_SESSION_DIR "/tmp/pass-agent-$USER"

    # Exported for this function's own scope only (and the commands it calls);
    # fish restores the prior value on return, so nothing leaks into the
    # interactive shell's environment.
    set -lx PROTON_PASS_SESSION_DIR $PROTON_PASS_SESSION_DIR

    if not pass-cli info >/dev/null 2>&1
        pass-cli logout --force >/dev/null 2>&1
        set -l pat (secret-tool lookup service proton-pass-cli account $PASS_PAT_KEYRING_ACCOUNT)
        if test -z "$pat"
            echo "pass_secret: no access token in the keyring for account $PASS_PAT_KEYRING_ACCOUNT" >&2
            return 1
        end
        if not env PROTON_PASS_PERSONAL_ACCESS_TOKEN=$pat pass-cli login >/dev/null 2>&1
            echo 'pass_secret: login failed' >&2
            return 1
        end
    end

    set -l out (env PROTON_PASS_AGENT_REASON="$reason" \
        pass-cli item view --vault-name $PASS_VAULT_NAME --item-title $item --field $field \
        | string collect)
    if test $status -ne 0
        echo 'pass_secret: pass-cli item view failed' >&2
        return 1
    end
    echo $out
end
