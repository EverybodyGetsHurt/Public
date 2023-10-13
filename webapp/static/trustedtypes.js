// trustedtypes.js
// Define the policy for trustedTypes
const policy = window.trustedTypes?.createPolicy('default', {
    createHTML: (s) => s,
    createScriptURL: (s) => s,
    createScript: (s) => s,
});
window.trustedTypes = policy;

