# sdk_voice_toggle.py
import os
import anyio
from claude_code_sdk import query, ClaudeCodeOptions

async def voice_toggle():
    options = ClaudeCodeOptions(cwd=os.getcwd())
    
    prompt = "NEW TASK: Add voice engine toggle to CogTwin. Step 1: In config.yaml add 'voice:' section with 'engine: venom' as default. Step 2: In cog_twin.py find the VenomVoice import and modify to conditionally import EnterpriseVoice from enterprise_voice.py when cfg('voice.engine')=='enterprise', otherwise use VenomVoice. Step 3: Verify both voice classes have compatible build_prompt interface. Step 4: Test server starts with voice.engine set to venom. Step 5: Change config to enterprise and test again. Report all file changes made."
    
    async for message in query(prompt=prompt, options=options):
        print(message)

if __name__ == "__main__":
    anyio.run(voice_toggle)