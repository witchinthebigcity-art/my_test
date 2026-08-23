(function () {
    const SUBSCRIPT_DIGITS = { '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4', '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9' };
    const SUPERSCRIPT_DIGITS = { '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9' };

    function replacePowerParentheses(source) {
        let result = '';
        for (let index = 0; index < source.length; index++) {
            if (source[index] !== '^' || source[index + 1] !== '(') {
                result += source[index];
                continue;
            }
            let depth = 1;
            let end = index + 2;
            while (end < source.length && depth) {
                if (source[end] === '(') depth++;
                if (source[end] === ')') depth--;
                end++;
            }
            if (depth) {
                result += source[index];
                continue;
            }
            result += `^{${source.slice(index + 2, end - 1)}}`;
            index = end - 1;
        }
        return result;
    }

    function normaliseLatex(value) {
        let formula = String(value || '').trim();
        formula = formula.replace(/≥q/g, '≥').replace(/≤q/g, '≤').replace(/=\s*>/g, '\\Rightarrow ');
        formula = formula.replace(/(?<![A-Za-zА-Яа-яЁё])pi(?![A-Za-zА-Яа-яЁё])/gi, '\\pi');
        formula = formula.replace(/π\s*/g, '\\pi ');
        formula = formula.replace(/(\d),(\d)/g, '$1{,}$2');
        formula = formula.replace(/[₀-₉]+/g, (digits) => `_{${[...digits].map((digit) => SUBSCRIPT_DIGITS[digit]).join('')}}`);
        formula = formula.replace(/[⁰¹²³⁴⁵⁶⁷⁸⁹]+/g, (digits) => `^{${[...digits].map((digit) => SUPERSCRIPT_DIGITS[digit]).join('')}}`);
        formula = formula.replace(/²/g, '^{2}').replace(/³/g, '^{3}');
        formula = formula.replace(/√\(([^()]*)\)/g, '\\sqrt{$1}');
        formula = formula.replace(/√([A-Za-zА-Яа-я0-9.,]+)/g, '\\sqrt{$1}');
        formula = replacePowerParentheses(formula);
        formula = formula.replace(/\^\s*-\s*([A-Za-z0-9]+)/g, '^{-$1}');
        formula = formula.replace(/\^\s*([0-9]+\s*\/\s*[0-9]+)/g, '^{$1}');
        formula = formula.replace(/\^\s*([0-9]+(?:[.,][0-9]+)?)/g, '^{$1}');
        formula = formula.replace(/log__\\sqrt\{([^}]+)\}/gi, '\\log_{\\sqrt{$1}}');
        formula = formula.replace(/\blog_([A-Za-z0-9.,]+)\s*\/\s*([A-Za-z0-9.,]+)/gi, '\\log_{\\frac{$1}{$2}}');
        formula = formula.replace(/\blog_([A-Za-zА-Яа-я0-9.,]+)\s*\(([^()]*)\)/gi, '\\log_{$1}($2)');
        formula = formula.replace(/\blog_([A-Za-zА-Яа-я0-9.,]+)/gi, '\\log_{$1}');
        formula = formula.replace(/_([А-Яа-яЁё]+)/g, '_{\\mathrm{$1}}');
        formula = formula.replace(/_([A-Za-z0-9]+)/g, '_{$1}');
        formula = formula.replace(/(?<!\\)\blog\b/gi, '\\log');
        formula = formula.replace(/(?<!\\)\bln\b/gi, '\\ln');
        formula = formula.replace(/(?<!\\)\bsin\b/gi, '\\sin');
        formula = formula.replace(/(?<!\\)\bcos\b/gi, '\\cos');
        formula = formula.replace(/(?<!\\)\btan\b/gi, '\\tan');
        formula = formula.replace(/(?<![A-Za-z])tg\b/gi, '\\operatorname{tg}');
        formula = formula.replace(/(?<![A-Za-z])ctg\b/gi, '\\operatorname{ctg}');
        formula = formula.replace(/°/g, '^{\\circ}');
        formula = formula.replace(/\^\s*([A-Za-z])/g, '^{$1}');
        formula = formula.replace(/\s*·\s*/g, ' \\cdot ');
        formula = formula.replace(/(\^\{[^}]+\})\s+([A-Za-z])/g, '$1\\,$2');
        return formula.replace(/[ \t]{2,}/g, ' ').trim();
    }

    function looksLikeFormula(value) {
        const text = String(value || '').trim();
        if (!text || /[А-Яа-яЁё]{3,}/.test(text)) return false;
        return /[0-9A-Za-zπ√=<>≤≥+\-*/^_()°·]/.test(text);
    }

    function stashInlineAssignments(text, stash) {
        const symbol = '[A-Za-z](?:_[A-Za-z0-9]+|[₀-₉]+)?';
        const expression = '[A-Za-z0-9π√_₀-₉⁰¹²³⁴⁵⁶⁷⁸⁹.,()+\\-*/·\\s]+';
        const boundary = `(?=\\s+(?:при|если|где)(?=\\s|[,.;?!]|$)|,\\s*${symbol}\\s*=|[;?!]|\\.\\s|$)`;
        const assignment = new RegExp(`(${symbol}\\s*=\\s*${expression}?)${boundary}`, 'gi');
        return text.replace(assignment, (match) => {
            const trailingSpace = match.match(/\s+$/)?.[0] || '';
            const trimmed = match.trim();
            const punctuation = trimmed.match(/[.;]$/)?.[0] || '';
            const formula = punctuation ? trimmed.slice(0, -1).trimEnd() : trimmed;
            return formula ? `${stash(formula)}${punctuation}${trailingSpace}` : match;
        });
    }

    function prepareMathText(value) {
        let text = String(value || '')
            .replace(/≥q/g, '≥')
            .replace(/≤q/g, '≤')
            .replace(/=\s*>/g, '⇒')
            .replace(/(?<![A-Za-zА-Яа-яЁё])pi(?![A-Za-zА-Яа-яЁё])/gi, 'π');
        const formulas = [];
        const stash = (formula) => {
            const marker = `\uE000${formulas.length}\uE001`;
            formulas.push(normaliseLatex(formula));
            return marker;
        };

        text = text.replace(/\$\$([\s\S]*?)\$\$|\$([^$]+)\$/g, (_match, display, inline) => stash(display ?? inline));
        // A lone dollar sign is a malformed delimiter, not part of a school task.
        // Removing only unmatched delimiters prevents strings such as "$T = ..."
        // from being shown literally while leaving the source question untouched.
        text = text.replace(/\$/g, '');
        if (looksLikeFormula(text)) return `$${normaliseLatex(text)}$`;

        // Mixed prose and formulas are common in the task sheet. Render assignment
        // fragments separately so words and variables keep a readable visual gap.
        text = stashInlineAssignments(text, stash);

        text = text.replace(/√\(([^()]*)\)/g, (_match, radicand) => stash(`\\sqrt{${radicand}}`));
        text = text.replace(/√([A-Za-zА-Яа-я0-9.,]+)/g, (_match, radicand) => stash(`\\sqrt{${radicand}}`));
        text = text.replace(/\blog\s*_+\s*√\(([^()]*)\)\s*\(([^()]*)\)/gi, (_match, base, argument) => stash(`\\log_{\\sqrt{${base}}}(${argument})`));
        text = text.replace(/\blog\s*(?:_|\s)\s*([₀-₉A-Za-zαβγ.,]+)\s*\(([^()]*)\)/gi, (_match, base, argument) => {
            const baseText = [...base].map((character) => SUBSCRIPT_DIGITS[character] ?? character).join('');
            return stash(`\\log_{${baseText}}(${argument})`);
        });
        text = text.replace(/\b(sin|cos|tan|tg|ctg|ln)\s*\(([^()]*)\)/gi, (_match, name, argument) => stash(`${name}(${argument})`));
        text = text.replace(/\b([A-Za-zА-Яа-яЁё]+)_([A-Za-zА-Яа-яЁё0-9]+)/g, (_match, symbol, index) => {
            const safeIndex = /[А-Яа-яЁё]/.test(index) ? `\\mathrm{${index}}` : index;
            return stash(`${symbol}_{${safeIndex}}`);
        });
        text = text.replace(/([A-Za-z0-9А-Яа-яЁё)])\^\s*(-?\s*[0-9]+(?:[.,][0-9]+)?|[A-Za-z])/g, (_match, base, power) => stash(`${base}^{${power.replace(/\s+/g, '')}}`));

        return text.replace(/\uE000(\d+)\uE001/g, (_match, index) => `$${formulas[Number(index)]}$`);
    }

    function setMathContent(element, value) {
        if (!element) return;
        element.textContent = prepareMathText(value);
        if (typeof renderMathInElement === 'function') {
            renderMathInElement(element, {
                delimiters: [{ left: '$$', right: '$$', display: true }, { left: '$', right: '$', display: false }],
                throwOnError: false,
                strict: false,
            });
        }
    }

    window.normaliseLatex = normaliseLatex;
    window.prepareMathText = prepareMathText;
    window.stashInlineAssignments = stashInlineAssignments;
    window.setMathContent = setMathContent;
})();
