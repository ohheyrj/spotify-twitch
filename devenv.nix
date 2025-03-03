{ pkgs, lib, config, inputs, ... }:

{
  languages.python = {
    enable = true;
    venv.enable = true;
  };
  git-hooks.hooks.gitleaks = {
    enable = true;
    entry = "gitleaks protect";
  };
}
