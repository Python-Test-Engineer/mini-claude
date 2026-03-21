 I did a much simpler one-shot prompt for the slash command feature.

 I forgot what I did so I asked Claude to create a prompt that would create a slash command feature:
 
 ---

 Add slash command support to mini_claude.py.                                
  
  - If the user types /commandname (optionally followed by arguments), look   
  for a file at slash_commands/commandname.md relative to the script
  - Load that file's contents and use it as the prompt sent to the API instead
   of the raw user input
  - Support a $ARGUMENTS placeholder in the .md file that gets replaced with
  anything typed after the command name (like /fix some bug → $ARGUMENTS      
  becomes "some bug")
  - If no matching file is found, print a warning in yellow and skip the API  
  call
  - Print a yellow [slash /name] label when a command is resolved

  Also add a built-in /hello command that prints a colorful block-letter      
  "HELLO" in ANSI colors directly to the terminal (no API call needed). Each  
  letter should be a different color using # characters for the pixels.       

  The slash resolution should happen in the outer loop before appending to    
  history. Built-in commands (like /hello) should be checked first and        
  short-circuit the loop entirely.

  ---