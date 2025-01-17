# Get the AppImage tool
sudo apt install coreutils binutils patchelf desktop-file-utils fakeroot fuse squashfs-tools strace util-linux zsync libgdk-pixbuf2.0-dev -y

wget --no-check-certificate --quiet "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-$(uname -m).AppImage" -O $GITHUB_WORKSPACE/appimagetool
chmod +x $GITHUB_WORKSPACE/appimagetool
echo "APPIMAGETOOL_LOCATION=$GITHUB_WORKSPACE/appimagetool" >> $GITHUB_ENV

# Get the AppImage builder
sudo pip3 install git+https://github.com/AppImageCrafters/appimage-builder.git@9733877eed75aea0fa8e9a1cd26c22d77a10aa4a
echo "APPIMAGEBUILDER_LOCATION=appimage-builder" >> $GITHUB_ENV
# wget --no-check-certificate --quiet -O $GITHUB_WORKSPACE/appimage-builder-x86_64.AppImage https://github.com/AppImageCrafters/appimage-builder/releases/download/v1.1.0/appimage-builder-1.1.0-x86_64.AppImage
# chmod +x appimage-builder-x86_64.AppImage
# echo "APPIMAGEBUILDER_LOCATION=$GITHUB_WORKSPACE/appimage-builder-x86_64.AppImage" >> $GITHUB_ENV

# Make sure these tools can be found on the path
echo "$GITHUB_WORKSPACE" >> $GITHUB_PATH
