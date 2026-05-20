/**
 * @module slash-commands
 *
 * Slash command system for the terminal.
 *
 * Provides /clear, /help, /cost, /status, /compact commands.
 * Local commands execute client-side; remote commands are forwarded to the server.
 *
 * Depends on: common.js (Board namespace)
 * Registers:  Board.slashCommands
 */
"use strict";

(function () {
  var esc = Board.util.esc;

  /**
   * Registry of supported slash commands.
   * type: 'local' = client-only, 'remote' = server relay, 'local+remote' = both
   */
  var SLASH_COMMANDS = {
    '/clear':   { description: 'Reset and Context Reset', type: 'local+remote', handler: handleClear },
    '/help':    { description: 'Enabled command list',       type: 'local',        handler: handleHelp },
    '/cost':    { description: 'Check out the current session cost',                type: 'remote',       handler: handleRemoteCommand },
    '/status':  { description: 'Check the current session status',                type: 'remote',       handler: handleRemoteCommand },
    '/compact': { description: 'Context Compression',                      type: 'remote',       handler: handleRemoteCommand },
    '/login':   { description: 'Account authentication and conversion',                  type: 'remote',       handler: handleRemoteCommand },
  };

  /**
   * Routes a slash command to the appropriate handler.
   * Blocks slash commands in workflow mode.
   * @param {string} text - full input text starting with '/'
   * @param {object} ctx - context object with { isWorkflowMode, appendSystemMessage, appendHtmlBlock, appendErrorMessage, clearOutput, postJson }
   */
  function handleSlashCommand(text, ctx) {
    if (ctx.isWorkflowMode) {
      return;
    }

    var parts = text.trim().split(/\s+/);
    var cmd = parts[0].toLowerCase();
    var entry = SLASH_COMMANDS[cmd];

    if (!entry) {
      return;
    }

    entry.handler(cmd, parts.slice(1), ctx);
  }

  /**
   * Handles /clear: clears screen output and sends context reset to server.
   */
  function handleClear(cmd, args, ctx) {
    ctx.clearOutput();
    ctx.postJson("/terminal/command", { command: cmd }).catch(function () {
      /* silent */
    });
  }

  /**
   * Handles /help: renders available slash commands as an HTML table.
   */
  function handleHelp(cmd, args, ctx) {
    var rows = "";
    Object.keys(SLASH_COMMANDS).forEach(function (name) {
      var entry = SLASH_COMMANDS[name];
      rows += "<tr><td>" + name + "</td><td>" + entry.description + "</td></tr>";
    });
    var html = "<table><thead><tr><th>Name</th><th>Name</th></tr></thead>"
      + "<tbody>" + rows + "</tbody></table>";
    ctx.appendHtmlBlock(html, "term-slash-result");
  }

  /**
   * Handles remote-only slash commands (/cost, /status, /compact).
   */
  function handleRemoteCommand(cmd, args, ctx) {
    ctx.postJson("/terminal/command", { command: cmd }).catch(function (err) {
      ctx.appendErrorMessage("[Error] " + err.message);
    });
  }

  // ── Register on Board namespace ──
  Board.slashCommands = {
    handle: handleSlashCommand,
    SLASH_COMMANDS: SLASH_COMMANDS
  };
})();
