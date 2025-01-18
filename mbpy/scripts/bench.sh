#!/bin/sh

# Function to measure time of a command
mbtime() {
    if [ $# -eq 0 ] || [ "$1" = "--help" ]; then
        echo "Usage: mbtime <command>"
        return 1
    fi

    # Use gdate on macOS for nanosecond precision
    if command -v gdate >/dev/null 2>&1; then
        DATE_CMD="gdate"
    else
        DATE_CMD="date"
    fi

    start_time=$($DATE_CMD +%s.%N)
    eval "$@"
    status_=$?
    end_time=$($DATE_CMD +%s.%N)
    
    if command -v bc >/dev/null 2>&1; then
        elapsed=$(printf "%.3f" "$(echo "$end_time - $start_time" | bc)")
    else
        elapsed=$((end_time - start_time))
    fi

    printf "\nElapsed Time: %s seconds\n" "$elapsed"
    return $status_
}



# Keep existing mbtime() function

mtrepl() {
    # Initialize history
    typeset -a hist
    typeset -i histindex
    hist=()
    histindex=-1
    cmd="$@"
    if [ -n "$cmd" ]; then
        hist+=("$cmd")
        histindex=${#hist[@]}
        mbtime "$cmd"
    fi

    # Zsh widgets for history navigation
    histbackward() {
        [[ $histindex -ge 0 ]] && {
            ((histindex--))
            [[ $histindex -ge 0 ]] && {
                BUFFER="${hist[$histindex]}"
                CURSOR=${#BUFFER}
            } || {
                BUFFER=""
                CURSOR=0
            }
        }
        zle reset-prompt
    }

    histforward() {
        [[ $histindex -lt $((${#hist[@]} - 1)) ]] && {
            ((histindex++))
            BUFFER="${hist[$histindex]}"
            CURSOR=${#BUFFER}
        } || {
            ((histindex++))
            BUFFER=""
            CURSOR=0
        }
        zle reset-prompt
    }

    # Shell-specific setup for Zsh
    if [ -n "$ZSH_VERSION" ]; then
        autoload -U up-line-or-beginning-search
        autoload -U down-line-or-beginning-search
        
        # Create widgets
        zle -N up-line-or-beginning-search
        zle -N down-line-or-beginning-search
        zle -N histbackward
        zle -N histforward
        
        # Bind keys
        bindkey "^[[A" histbackward
        bindkey "^[[B" histforward
        
        cleanup() {
            bindkey "^[[A" up-line-or-beginning-search
            bindkey "^[[B" down-line-or-beginning-search
        }
    else
        # Bash bindings remain unchanged
        bind -x '"\e[A":histbackward'
        bind -x '"\e[B":histforward'
        
        cleanup() {
            bind -r "\e[A"
            bind -r "\e[B"
        }
    fi

    trap cleanup EXIT INT TERM

    # Keep existing REPL loop
    while true; do
        printf ">> "
        read -r input
        [ $? -ne 0 ] && break
        [ -z "$input" ] && continue
        case "$input" in
            history)
                printf "%s\n" "${hist[@]}"
                ;;
            clear)
                hist=()
                histindex=-1
                echo "History cleared."
                ;;
            exit)
                break
                ;;
            *)
                hist+=("$input")
                histindex=${#hist[@]}
                mbtime "$input"
                ;;
        esac
    done
}

alias mt='mtrepl'
