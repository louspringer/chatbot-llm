"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = require("vscode");
const child_process_1 = require("child_process");
const path = require("path");
const fs = require("fs");
const os = require("os");
function activate(context) {
    console.log('Cursor SPARQL Tools extension is now active');
    let disposable = vscode.commands.registerCommand('cursor-sparql.runQuery', async () => {
        // Get the active text editor
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showErrorMessage('No active editor');
            return;
        }
        // Get the selected text or entire document
        const selection = editor.selection;
        const query = selection.isEmpty ?
            editor.document.getText() :
            editor.document.getText(selection);
        // Get the workspace folder
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            vscode.window.showErrorMessage('No workspace folder open');
            return;
        }
        try {
            // Create a temporary file for the query
            const tmpFile = path.join(os.tmpdir(), 'query.rq');
            fs.writeFileSync(tmpFile, query);
            // Get list of .ttl files in workspace
            const ttlFiles = await vscode.workspace.findFiles('**/*.ttl');
            if (ttlFiles.length === 0) {
                vscode.window.showErrorMessage('No .ttl files found in workspace');
                return;
            }
            // Let user select which .ttl file to query
            const ttlFile = await vscode.window.showQuickPick(ttlFiles.map(file => ({
                label: path.basename(file.fsPath),
                description: vscode.workspace.asRelativePath(file),
                fsPath: file.fsPath
            })), { placeHolder: 'Select ontology file to query' });
            if (!ttlFile) {
                return;
            }
            // Run the SPARQL query using Jena
            const sparql = (0, child_process_1.spawn)('sparql', [
                '--data', ttlFile.fsPath,
                '--query', tmpFile,
                '--results', 'json'
            ]);
            let output = '';
            let error = '';
            sparql.stdout.on('data', (data) => {
                output += data;
            });
            sparql.stderr.on('data', (data) => {
                error += data;
            });
            sparql.on('close', (code) => {
                // Clean up temp file
                fs.unlinkSync(tmpFile);
                if (code !== 0) {
                    vscode.window.showErrorMessage(`SPARQL query failed: ${error}`);
                    return;
                }
                try {
                    // Parse and format the JSON results
                    const results = JSON.parse(output);
                    const formatted = JSON.stringify(results, null, 2);
                    // Show results in new editor
                    vscode.workspace.openTextDocument({
                        content: formatted,
                        language: 'json'
                    }).then(doc => {
                        vscode.window.showTextDocument(doc, {
                            viewColumn: vscode.ViewColumn.Beside
                        });
                    });
                }
                catch (e) {
                    vscode.window.showErrorMessage(`Failed to parse results: ${e}`);
                }
            });
        }
        catch (e) {
            vscode.window.showErrorMessage(`Error running query: ${e}`);
        }
    });
    context.subscriptions.push(disposable);
}
function deactivate() { }
//# sourceMappingURL=extension.js.map
