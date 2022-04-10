PLUGIN_DIR='' # set your keyboard-layouter path

if [ -z "$PLUGIN_DIR" ]; then
    echo 'Set your keyboard-layouter path to PLUGIN_DIR in install.sh';
	exit 1
fi

if [ "$(uname)" == 'Darwin' ]; then
	echo 'Mac'
    DEST_DIR="$HOME/Library/Application Support/kicad/scripting/plugins/"

    if [ ! -d "$DEST_DIR" ]; then
        echo 'create dir'
        mkdir -p "$DEST_DIR"
    fi

    ln -s "$PLUGIN_DIR/keyboard_layouter.py" "$DEST_DIR"
elif [ "$(expr substr $(uname -s) 1 5)" == 'Linux' ]; then
	echo 'Linux'
    DEST_DIR="$HOME/.kicad/scripting/plugins/"

    if [ ! -d "$DEST_DIR" ]; then
        echo 'create dir'
        mkdir -p "$DEST_DIR"
    fi

    ln -s "$PLUGIN_DIR/keyboard_layouter.py" "$DEST_DIR"

else
	echo "Your platform ($(uname -a)) is not supported."
	exit 1
fi


