{ lib
, stdenv
, fetchurl
, dpkg
}:

stdenv.mkDerivation rec {
  pname = "obs-ptz";
  version = "0.18.2";

  src = fetchurl {
    url = "https://github.com/glikely/obs-ptz/releases/download/v${version}/obs-ptz-${version}-x86_64-linux-gnu.deb";
    sha256 = "sha256-wu42LYQslZB9ZY2nMQvUf5cWS6gLlQPB9UWA2cx/fa4=";
  };

  nativeBuildInputs = [ dpkg ];

  unpackPhase = ''
    dpkg-deb -x $src .
  '';

  installPhase = ''
    runHook preInstall
    
    mkdir -p $out/lib/obs-plugins
    mkdir -p $out/share/obs/obs-plugins
    
    # Copy plugin files from wherever they are in the deb
    if [ -d usr/lib/x86_64-linux-gnu/obs-plugins ]; then
      cp -r usr/lib/x86_64-linux-gnu/obs-plugins/* $out/lib/obs-plugins/
    fi
    
    if [ -d usr/lib/obs-plugins ]; then
      cp -r usr/lib/obs-plugins/* $out/lib/obs-plugins/
    fi
    
    if [ -d usr/share/obs/obs-plugins ]; then
      cp -r usr/share/obs/obs-plugins/* $out/share/obs/obs-plugins/
    fi
    
    runHook postInstall
  '';

  meta = with lib; {
    description = "PTZ camera control plugin for OBS Studio";
    homepage = "https://github.com/glikely/obs-ptz";
    license = licenses.gpl2Plus;
    platforms = platforms.linux;
    maintainers = [ ];
  };
}