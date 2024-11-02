# If linux apt install coq else brew install coq
if [ "$(uname)" == "Darwin" ]; then
    brew install coq
    brew install opam
else
    sudo apt-get install coq
    sudo apt-get install opam
fi