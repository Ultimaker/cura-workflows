# Get the AppImage tool
sudo apt install coreutils binutils patchelf desktop-file-utils fakeroot fuse squashfs-tools strace util-linux zsync libgdk-pixbuf2.0-dev -y

wget --no-check-certificate --quiet "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-$(uname -m).AppImage" -O $GITHUB_WORKSPACE/appimagetool
chmod +x $GITHUB_WORKSPACE/appimagetool
echo "APPIMAGETOOL_LOCATION=$GITHUB_WORKSPACE/appimagetool" >> $GITHUB_ENV

# Get the AppImage builder
sudo pip3 install git+https://github.com/Frederic98/appimage-builder.git
echo "APPIMAGEBUILDER_LOCATION=appimage-builder" >> $GITHUB_ENV

# Make sure these tools can be found on the path
echo "$GITHUB_WORKSPACE" >> $GITHUB_PATH
