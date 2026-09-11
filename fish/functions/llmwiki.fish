function llmwiki --description 'llmwiki, with the OpenRouter API key injected only when the verb needs it'
    set -l exe (command -s llmwiki)
    if test -z "$exe"
        echo 'llmwiki: not installed' >&2
        return 127
    end

    # First non-flag argument, skipping the value after --kb.
    set -l no_key_verbs '' where init lint status
    set -l verb ''
    set -l skip_next 0
    for arg in $argv
        if test $skip_next -eq 1
            set skip_next 0
            continue
        end
        if test "$arg" = --kb
            set skip_next 1
            continue
        end
        if not string match --quiet -- '-*' $arg
            set verb $arg
            break
        end
    end

    if contains -- $verb $no_key_verbs
        $exe $argv
        return $status
    end

    set -l key (llm_wiki_api_key)
    if test -z "$key"
        echo 'llmwiki: could not retrieve the api key' >&2
        return 1
    end
    env LLM_WIKI_API_KEY=$key $exe $argv
end
