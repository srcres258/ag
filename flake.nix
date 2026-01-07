{
  description = "Nix flake configurations for this project";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = {
    self,
    nixpkgs,
    flake-utils
  }: flake-utils.lib.eachDefaultSystem (system: let
    pkgs = import nixpkgs {
      inherit system;
    };

    python = pkgs.python312;
    pythonEnv = pkgs.python312Packages;

    pname = "ag";
    version = "0.1.0";
    ag = pythonEnv.buildPythonApplication {
      inherit pname version;

      src = ./.;

      propagatedBuildInputs = with pythonEnv; [
        openai
        termcolor
        prompt-toolkit
      ];
      nativeBuildInputs = with pythonEnv; [
        hatchling
      ];

      format = "pyproject";

      doCheck = true;

      meta = with pkgs.lib; {
        description = "A command-line AI assistant";
        homepage = "https://github.com/srcres258/ag";
        license = licenses.mit;
        maintainers = with maintainers; [ srcres258 ];
      };
    };
  in {
    packages.default = ag;

    apps.default = {
      type = "app";
      program = "${ag}/bin/ag";
    };

    devShells.default = pkgs.mkShell {
      buildInputs = [ python ] ++ ag.propagatedBuildInputs;
    };
  });
}
