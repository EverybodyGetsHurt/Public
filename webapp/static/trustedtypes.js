// trustedtypes.js
// Define the policy for trustedTypes
const policy = window.trustedTypes?.createPolicy('default', {
    createHTML: (s) => {
        // Specific handling for autoclosealerts.js content
        if (s.includes('alert') && s.includes('close')) {
            return s;
        }

        // Specific handling for jQuery content
        if (s.includes('<') && s.includes('>')) {
            return s;
        }

        // For other cases, you can add more conditions or keep it as is
        return s;
    },
    createScriptURL: (s) => {
        // The original functionality is retained
        return s;
    },
    createScript: (s) => {
        // The original functionality is retained
        return s;
    },
});

window.trustedTypes = policy;
