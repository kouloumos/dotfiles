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
            # Add the overlay so obs-ptz-plugin is available in pkgs                                                                       
            { nixpkgs.overlays = [ self.overlays.default ]; }                                                                              
          ];                                                                                                                               
        };                                                                                                                                 
      };                                                                                                                                   
  }