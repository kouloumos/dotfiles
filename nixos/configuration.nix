# Edit this configuration file to define what should be installed on
# your system. Help is available in the configuration.nix(5) man page, on
# https://search.nixos.org/options and in the NixOS manual (`nixos-help`).

{ config, lib, pkgs, inputs, unstable, enableObsPtzPlugin, ... }:

{
  imports =
    [ 
      # Include the results of the hardware scan.
      ./hardware-configuration.nix
      # inputs.my-toolkit.nixosModules.default
    ];

  # Use the systemd-boot EFI boot loader.
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;
  boot.kernelPackages = pkgs.linuxPackages_latest;
  boot.kernelModules = [ "v4l2loopback" ];
  # Using the Virtual Camera https://nixos.wiki/wiki/OBS_Studio
  boot.extraModulePackages = with config.boot.kernelPackages; [ v4l2loopback ];
  boot.extraModprobeConfig = ''
    options v4l2loopback devices=1 video_nr=10 card_label="Tenveo Cam" exclusive_caps=1
  '';
  security.polkit.enable = true;

  # luks setup
  boot.initrd.luks.devices = {
    luksCrypted = {
      device = "/dev/nvme0n1p2";
      preLVM = true; # Unlock before activating LVM
    };
  };
  # lets your x86_64 machine run aarch64 (ARM) binaries by
  # transparently routing them through QEMU emulation.
  # Without it, Nix can't evaluate or build packages for the Pi's architecture
  boot.binfmt.emulatedSystems = [ "aarch64-linux" ];

  nix.settings.experimental-features = [ "nix-command" "flakes" ];
  nix.settings.trusted-users = [ "root" "kouloumos" ];

  programs.bash = {
    shellAliases = {
      update-unstable = "cd /etc/nixos && sudo nix flake lock --update-input nixpkgs-unstable";
      update-toolkit = "sudo nix flake lock /etc/nixos --update-input my-toolkit && rebuild";
      rebuild = "sudo nixos-rebuild switch";
      nixos = "code /etc/nixos/configuration.nix";
      flakes = "code /etc/nixos/flake.nix";
      git-config= "git config user.email 'kouloumosa@gmail.com' && git config user.name 'kouloumos'";
      lid-lock = "systemd-inhibit --what=handle-lid-switch --why=\"keep awake\" sleep infinity &";
      lid-unlock = "kill %1";
      cam-on = "systemctl --user start tenveo-cam";
      cam-off = "systemctl --user stop tenveo-cam";
    };

    interactiveShellInit = ''
    # Checkout a PR (defaults to 'upstream', can specify remote)
    checkout_pr() {
      local pr_num=$1
      local remote=''${2:-upstream}
      
      if [ -z "$pr_num" ]; then
        echo "Usage: checkout_pr <PR_NUMBER> [REMOTE]"
        echo "Example: checkout_pr 148"
        echo "Example: checkout_pr 148 origin"
        return 1
      fi
      
      git fetch $remote pull/$pr_num/head && wt --last pr-$pr_num --base FETCH_HEAD
    }
  '';
  };

  #   systemctl start tenveo-cam   # before a meeting
  #   systemctl stop  tenveo-cam   # after — frees device, saves battery
  systemd.user.services.tenveo-cam = {
    description = "Tenveo camera → v4l2 virtual webcam";
    serviceConfig = {
      ExecStart = pkgs.writeShellScript "tenveo-cam" ''
        exec ${pkgs.ffmpeg}/bin/ffmpeg -nostdin -hide_banner -loglevel warning \
          -rtsp_transport tcp -fflags nobuffer -flags low_delay \
          -i rtsp://192.168.1.200:554/live/av0 \
          -pix_fmt yuv420p -f v4l2 /dev/video10
      '';
      Restart = "on-failure";
      RestartSec = 3;
    };
  };

  networking.hostName = "kouloumos"; # Define your hostname.
  # Pick only one of the below networking options.
  # networking.wireless.enable = true;  # Enables wireless support via wpa_supplicant.
  networking.networkmanager.enable = true;  # Easiest to use and most distros use this by default.
  # for using PTZ camera on the same network
  # Create a persistent NetworkManager connection profile for PTZ camera
  environment.etc."NetworkManager/system-connections/Camera-Ethernet.nmconnection" = {
    mode = "0600";
    user = "root";
    group = "root";
    text = ''
      [connection]
      id=Camera-Ethernet
      # You can generate a new UUID by running `uuidgen` in a terminal, 
      # or use this fresh one I generated for you:
      uuid=563d1209-556b-4f91-9e7c-871026052345
      type=802-3-ethernet
      autoconnect=true

      [ipv4]
      method=manual
      address1=192.168.0.100/24

      [ipv6]
      method=disabled

      [ethernet]
      # Binding to the MAC address ensures this config always finds the correct adaptor
      mac-address=XX:XX:XX:XX:XX:XX
    '';
  };

  # Configure network proxy if necessary
  # networking.proxy.default = "http://user:password@proxy:port/";
  # networking.proxy.noProxy = "127.0.0.1,localhost,internal.domain";

  # Select internationalisation properties.
  # i18n.defaultLocale = "en_US.UTF-8";
  # console = {
  #   font = "Lat2-Terminus16";
  #   keyMap = "us";
  #   useXkbConfig = true; # use xkb.options in tty.
  # };

  # Enable the X11 windowing system.
  services.xserver.enable = true;

  services.displayManager.gdm.enable = true;
  services.desktopManager.gnome.enable = true;
  
  # Configure keymap in X11
  # services.xserver.xkb.layout = "us";
  # services.xserver.xkb.options = "eurosign:e,caps:escape";

  # Enable CUPS to print documents.
  # services.printing.enable = true;

  # Enable sound.
  services.pulseaudio.enable = false;
  services.pipewire = {
    enable = true;
    alsa.enable = true;                                                                                                                                                                                                        
    alsa.support32Bit = true;                                                                                                                                                                                                  
    pulse.enable = true;
    wireplumber.enable = true;
  };

  hardware.bluetooth = {
    enable = true;                                                                                                                                                                                                             
    settings = {  
      General = {
        Experimental = true;  # better codec support (LC3, etc.)
      };                                                                                                                                                                                                                       
    };
  };

  # Enable touchpad support (enabled default in most desktopManager).
  # services.libinput.enable = true;

  # Define a user account. Don't forget to set a password with ‘passwd’.
  users.users.kouloumos = {
    isNormalUser = true;
    extraGroups = [ "wheel" "networkmanager" "docker" "video" "dialout"]; # Enable ‘sudo’ for the user.
    home = "/home/kouloumos";
    packages = with pkgs; [
      tree
    ];
  };

  my-toolkit.enable = true;
  # Optionally enable specific services
  my-toolkit.services = {
    media-renamer = true;
    ebook-organizer = true;
    residential-proxy = true;
    claude-session-monitor = true;
  };

  # Required: allow insecure squid (dependency of my-toolkit)                                                                            
  nixpkgs.config.permittedInsecurePackages = [                                                                                           
    "squid-6.8"   # For nixos-24.05                                                                                                      
    "squid-7.0.1" # For nixos-unstable (if you upgrade later)                                                                            
  ];       

  # https://wiki.nixos.org/wiki/KDE_Connect
  programs.kdeconnect = {
    enable = true;
    package = pkgs.gnomeExtensions.gsconnect;
  };
  programs.firefox = {                                                                                                                                                                                                                      
    enable = true;                                                                                                                                                                                                                          
    preferences = {                                                                                                                                                                                                                         
      "browser.tabs.unloadOnLowMemory" = true;
      "browser.low_commit_space_threshold_mb" = 4096;                                                                                                                                                                                       
      "browser.low_commit_space_threshold_percent" = 20;                                                                                                                                                                                    
      "browser.tabs.min_inactive_duration_before_unload" = 300000;                                                                                                                                                                          
    };                                                                                                                                                                                                                                      
  };         
  nixpkgs.config.allowUnfree = true;
  # List packages installed in system profile. To search, run:
  # $ nix search wget
  environment.systemPackages = with pkgs; [
    # Web-access CLIs (see the browser-scripting skill). page-read = URL->markdown
    # reader; playwright-run = raw Playwright scripting (screenshots, interaction).
    inputs.toolkit.packages.${pkgs.system}.page-read
    inputs.toolkit.packages.${pkgs.system}.playwright-run

     vim-full # vim with +clipboard (wayland) support; the default vim package is a minimal build without it
     wget
     git
     ffmpeg
     poppler-utils
     obsidian
     avahi
     gnomeExtensions.tiling-assistant
     gnomeExtensions.gsconnect
     pkgs.gnome-shell-extensions
     (vscode-with-extensions.override {
      vscodeExtensions = with vscode-extensions; [
        jnoortheen.nix-ide
        eamodio.gitlens # inline blame, file/line history, rich diff & compare views
        mhutchie.git-graph # visual commit graph
      ];
     })
     discord
     rustdesk
     v4l-utils # for virtual camera support
     zoom-us
     gh
     libreoffice
     # https://nixos.wiki/wiki/OBS_Studio
    ] ++ lib.optionals enableObsPtzPlugin [(unstable.wrapOBS {
        plugins = with unstable.obs-studio-plugins; [
          obs-pipewire-audio-capture
        ] ++ [ pkgs.obs-ptz-plugin ];
      })
   ];

  # Enable nix-ld to run dynamically linked executables (e.g., VS Code extensions)
  # that expect standard Linux library locations
  programs.nix-ld = {
    enable = true;
    libraries = with pkgs; [
      stdenv.cc.cc.lib
      zlib
      openssl
      util-linux
      glib
    ];
  };

  # Declarative GNOME extension configuration
  programs.dconf.enable = true;
  programs.dconf.profiles.user.databases = [{
    settings = {
      "org/gnome/shell/extensions/window-list" = {
        display-all-workspaces = false;
        show-on-all-monitors = true;
      };
    };
  }];

  # Some programs need SUID wrappers, can be configured further or are
  # started in user sessions.
  # programs.mtr.enable = true;
  # programs.gnupg.agent = {
  #   enable = true;
  #   enableSSHSupport = true;
  # };

  # List services that you want to enable:

  # Enable the OpenSSH daemon.
  services.openssh.enable = true;

  # Fingerprint reader (Goodix sensor in the power button).
  # Enroll via GNOME Settings -> Users -> Fingerprint Login, or `fprintd-enroll`.
  services.fprintd.enable = true;

  # Firmware updates via LVFS (Framework ships BIOS/EC updates through fwupd).
  services.fwupd.enable = true;

  services.avahi = {
    enable = true;
    hostName = "kouloumos-framework";
    nssmdns4 = true;
  };

  virtualisation.docker.enable = true;

  system.activationScripts.claude-skills = ''
    ln -sfn /home/kouloumos/personal_projects/dotfiles/skills /home/kouloumos/.claude/skills
    chown -h kouloumos:users /home/kouloumos/.claude/skills 
  '';
  system.activationScripts.claude-config = ''                                                                                                                  
    ln -sfn /home/kouloumos/personal_projects/dotfiles/CLAUDE.md /home/kouloumos/.claude/CLAUDE.md
    chown -h kouloumos:users /home/kouloumos/.claude/CLAUDE.md                                                                                                 
  '';

  # Open ports in the firewall.
  # networking.firewall.allowedTCPPorts = [ ... ];
  # networking.firewall.allowedUDPPorts = [ ... ];
  # Or disable the firewall altogether.
  # networking.firewall.enable = false;

  # Copy the NixOS configuration file and link it from the resulting system
  # (/run/current-system/configuration.nix). This is useful in case you
  # accidentally delete configuration.nix.
  # system.copySystemConfiguration = true;

  # This option defines the first version of NixOS you have installed on this particular machine,
  # and is used to maintain compatibility with application data (e.g. databases) created on older NixOS versions.
  #
  # Most users should NEVER change this value after the initial install, for any reason,
  # even if you've upgraded your system to a new NixOS release.
  #
  # This value does NOT affect the Nixpkgs version your packages and OS are pulled from,
  # so changing it will NOT upgrade your system - see https://nixos.org/manual/nixos/stable/#sec-upgrading for how
  # to actually do that.
  #
  # This value being lower than the current NixOS release does NOT mean your system is
  # out of date, out of support, or vulnerable.
  #
  # Do NOT change this value unless you have manually inspected all the changes it would make to your configuration,
  # and migrated your data accordingly.
  #
  # For more information, see `man configuration.nix` or https://nixos.org/manual/nixos/stable/options#opt-system.stateVersion .
  system.stateVersion = "24.11"; # Did you read the comment?

}

