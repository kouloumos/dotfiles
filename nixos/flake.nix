{                                                                                                                                        
    description = "My NixOS configuration";                                                                                                
                                                                                                                                           
    inputs = {                                                                                                                             
      nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";                                                                                    
      nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixos-unstable";                                                                        
      my-toolkit = {                                                                                                                       
        url = "path:/home/kouloumos/personal_projects/my-toolkit";                                                                         
      };

      # Web-access CLIs (page-read, playwright-run) — see the browser-scripting
      # skill. Same packages the team gets via `nix run`, pinned to a release.
      toolkit = {
        url = "github:schemalabz/toolkit/v2026.8.1";
      };                                                                                                                                   

      # Official Claude desktop app for Linux (beta), repackaged from
      # Anthropic's .deb. Not in nixpkgs yet (NixOS/nixpkgs#537215 still in
      # review) and upstream ships ~weekly with no self-update, so track the
      # flake and re-lock it to upgrade: `nix flake update claude-desktop`.
      claude-desktop = {
        url = "github:nmcbride/claude-desktop-nix";
        # It pins nixos-unstable; reuse ours instead of a second nixpkgs.
        inputs.nixpkgs.follows = "nixpkgs-unstable";
      };
    };                                                                                                                                     
                                                                                                                                           
    outputs = { self, nixpkgs, nixpkgs-unstable, my-toolkit, ... }@inputs:                                                                 
      let                                                                                                                                  
        system = "x86_64-linux";                                                                                                           
        pkgs = nixpkgs.legacyPackages.${system};                                                                                           
        unstable = nixpkgs-unstable.legacyPackages.${system};                                                                              
                                                                                                                                           
        # Configuration flags                                                                                                              
        enableObsPtzPlugin = true;                                                               
      in                                                                                                                                   
      {                                                                                                                                    
        # Custom packages                                                                                                                  
        packages.${system} = pkgs.lib.optionalAttrs enableObsPtzPlugin {                                                                   
          obs-ptz-plugin = unstable.callPackage ./pkgs/obs-ptz-plugin.nix { };                                                             
        };                                                                                                                                 
                                                                                                                                           
        # Overlay to make the plugin available in configuration.nix                                                                        
        overlays.default = final: prev: pkgs.lib.optionalAttrs enableObsPtzPlugin {                                                        
          obs-ptz-plugin = self.packages.${system}.obs-ptz-plugin;                                                                         
        };                                                                                                                                 
                                                                                                                                           
        nixosConfigurations.kouloumos = nixpkgs.lib.nixosSystem {                                                                          
          inherit system;                                                                                                                  
          specialArgs = {                                                                                                                  
            inherit inputs;           
            inherit enableObsPtzPlugin;                                                                                                     
            # Pass unfree config to both stable and unstable                                                                               
            unstable = import nixpkgs-unstable {                                                                                           
              system = "x86_64-linux";                                                                                                     
              config.allowUnfree = true;                                                                                                   
            };                                                                                                                             
          };                                                                                                                               
          modules = [                                                                                                                      
            ./configuration.nix                                                                                                            
            my-toolkit.nixosModules.default                                                                                                
            inputs.claude-desktop.nixosModules.default
            ({ pkgs, config, ... }: {
              programs.claude-desktop.enable = true;
              # Cowork's VM sandbox needs symlinks in /usr (the app probes
              # hard-coded FHS paths) plus vhost_vsock and kvm-group access.
              # Left off to keep /usr clean; Chat and Claude Code work without
              # it. Flip to true + reboot (vhost_vsock is =m) to try Cowork.
              programs.claude-desktop.cowork.enable = false;

              # The wrapper puts qemu on PATH unconditionally, but qemu only
              # runs Cowork's VM (~1.1 GB of new store paths, 29 guest-arch
              # emulators we would never use). Tie it to the flag above so the
              # two cannot drift: no Cowork, no qemu.
              programs.claude-desktop.package =
                let
                  base = inputs.claude-desktop.packages.${pkgs.system}.default;
                in
                if config.programs.claude-desktop.cowork.enable then
                  base.override { qemu = pkgs.qemu_kvm; }
                else
                  base.override { qemu = pkgs.emptyDirectory; };
            })
            # Add the overlay so obs-ptz-plugin is available in pkgs                                                                       
            { nixpkgs.overlays = [ self.overlays.default ]; }                                                                              
          ];                                                                                                                               
        };                                                                                                                                 
      };                                                                                                                                   
  }