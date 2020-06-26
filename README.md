# MKB-Syntax-Highlighting
Macro/Keybind Mod Syntax Highlighting for Sublime Text 3

**Custom syntax highlighting for Macro/Keybind Mod + Modules**

**Designed for Sublime Text 3**

*You could modify it to work on your own text editor, probably by using the regular expression matches and captures. You could also reference the minecraft hex color codes.*

**Set Up:**

There are 2 files: __MKB.yaml__ which is a YAML file, with the regexes and assigning scopes to them. __MKB.json__ is for the custom colors and rules. 

*Note that the menus might be different depending on your os, so you can always use the text editor's help, or ask me*

**Useful links:**

https://packagecontrol.io/installation

https://github.com/SublimeText/PackageDev/blob/master/README.md

You need to get PackageDev for this, by doing `Preferences > Package Control` and then type `Package Control: Install Package`, afterwards find `PackageDev` in the menu and install it. 

To install __MKB.yaml__, you need to go to `Tools > Developer > New Syntax...` and paste everything into the page, save it as MKB.sublime-syntax.

Next you need to add the custom colors in __MKB.json__, and to do that you go to. `Tools > Packages > Package Development > Edit Current Color Scheme...` Paste the entire json contents into the **Right Side** of the color scheme, for the user. 

**Usage:**

When opening a txt or rtf file (can be configured), if the first line is `$${` it will automatically change to `MKB` syntax. But if it doesnt work, then you can go to the bottom left corner, and click `User`, and change `Plain Text` to `MKB`. 

**How does it work?**

The new sublime syntax will recognize the actions, variables, parameters, iterators... of macro mod and common modules, using regex it assigns a scope to it. The scope is then assigned a color in the color scheme file, and then you get custom syntax highlighting!

**Others**

If there are any bugs, please tell me! My discord is TKM#6228. If there is any suggestions please tell me too! 
