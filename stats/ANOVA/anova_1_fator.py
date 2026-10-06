import pandas as pd
import scipy.stats as stats
import statsmodels.api as sm
from statsmodels.formula.api import ols
import statsmodels.stats.stattools as stattools
from IPython.display import Markdown

class ANOVA1Fator:
    def __init__(self, df, grupo, valor):
        self.df = df
        self.grupo = grupo
        self.valor = valor
    
    def anova(self):
        """
        Realiza ANOVA de um fator.

        Parâmetros:
            df: DataFrame com os dados.
            grupo: nome da coluna categórica (fator).
            valor: nome da coluna numérica (resposta).

        Retorna:
            Tabela ANOVA do statsmodels.
        """
        formula = f'{self.valor} ~ C({self.grupo})'
        modelo = ols(formula, data=self.df).fit()
        anova = sm.stats.anova_lm(modelo, typ=2)
        return anova    

    def summary(self, alpha=0.05):
        """
        Recria o sumário do statsmodels em Markdown com interpretações e testes de hipóteses.
        """
        formula = f'{self.valor} ~ C({self.grupo})'
        modelo = ols(formula, data=self.df).fit()

        def format_p(p):
            if pd.isna(p): return "NaN"
            return "<0.0001" if p < 0.0001 else f"{p:.4f}"

        resumo_dict = {
            "Dep. Variable": self.valor,
            "Model": "OLS",
            "Method": "Least Squares",
            "No. Observations": int(modelo.nobs),
            "Df Residuals": int(modelo.df_resid),
            "Df Model": int(modelo.df_model),
            "R-squared": f"{modelo.rsquared:.4f}",
            "Adj. R-squared": f"{modelo.rsquared_adj:.4f}",
            "F-statistic": f"{modelo.fvalue:.4f}",
            "Prob (F-statistic)": format_p(modelo.f_pvalue),
            "Log-Likelihood": f"{modelo.llf:.4f}",
            "AIC": f"{modelo.aic:.4f}",
            "BIC": f"{modelo.bic:.4f}"
        }
        resumo_df = pd.DataFrame(list(resumo_dict.items()), columns=["Métrica", "Valor"])
        resumo_md = resumo_df.to_markdown(index=False)

        niveis = sorted(self.df[self.grupo].dropna().astype(str).unique())
        ref = niveis[0] if len(niveis) > 0 else "Referência"

        hipoteses_md = f"""
## 2. Hipóteses testadas
**Teste global (estatística F):**
- $H_0: \mu_1 = \dots = \mu_k$ (todas as médias populacionais são iguais)
- $H_1:$ pelo menos uma média difere das demais

**Testes dos coeficientes (estatísticas t):**
Nível de referência: `{self.grupo} = {ref}` (Intercepto)
Nível de significância: $\\alpha = {alpha}$

- $H_0: \mu_j - \mu_{{{ref}}} = 0$ (a média do grupo é igual à do grupo de referência)
- $H_1: \mu_j - \mu_{{{ref}}} \\neq 0$
"""

        conf_int = modelo.conf_int(alpha=alpha)
        coefs = []
        for term in modelo.params.index:
            if term == 'Intercept':
                nome_limpo = f"Intercepto ({ref})"
            else:
                try:
                    nivel = term.split("[T.")[1].split("]")[0]
                    nome_limpo = f"{self.grupo} = {nivel}"
                except:
                    nome_limpo = term
            
            coef = modelo.params[term]
            std_err = modelo.bse[term]
            t = modelo.tvalues[term]
            p = modelo.pvalues[term]
            ci_low = conf_int.loc[term][0]
            ci_high = conf_int.loc[term][1]
            decisao = "Rejeita $H_0$" if p < alpha else "Não rejeita $H_0$"
            
            coefs.append({
                "Termo": nome_limpo,
                "Coeficiente": f"{coef:.4f}",
                "Std Err": f"{std_err:.4f}",
                "t": f"{t:.4f}",
                "P>|t|": format_p(p),
                f"IC {int((1-alpha)*100)}% Inferior": f"{ci_low:.4f}",
                f"IC {int((1-alpha)*100)}% Superior": f"{ci_high:.4f}",
                "Decisão": decisao
            })
            
        coefs_df = pd.DataFrame(coefs)
        coefs_md = coefs_df.to_markdown(index=False)

        residuos = modelo.resid
        jb, jbpv, skew, kurtosis = stattools.jarque_bera(residuos)
        try:
            omnibus, omnp = stats.normaltest(residuos)
        except ValueError:
            omnibus, omnp = float('nan'), float('nan')
            
        dw = stattools.durbin_watson(residuos)
        cond_no = modelo.condition_number

        diag_dict = {
            "Omnibus": f"{omnibus:.4f}",
            "Prob(Omnibus)": format_p(omnp),
            "Skew": f"{skew:.4f}",
            "Kurtosis": f"{kurtosis:.4f}",
            "Durbin-Watson": f"{dw:.4f}",
            "Jarque-Bera (JB)": f"{jb:.4f}",
            "Prob(JB)": format_p(jbpv),
            "Cond. No.": f"{cond_no:.4f}"
        }
        diag_df = pd.DataFrame(list(diag_dict.items()), columns=["Teste", "Valor"])
        diag_md = diag_df.to_markdown(index=False)

        if modelo.f_pvalue < alpha:
            decisao_f = f"Como o p-valor da estatística F ({format_p(modelo.f_pvalue)}) é menor que {alpha}, **rejeitamos a hipótese nula global**."
            conclusao = "Há evidências significativas de que pelo menos uma das médias difere das demais. É recomendado aplicar um teste *post hoc* (como o Tukey HSD) para identificar especificamente quais grupos são diferentes."
        else:
            decisao_f = f"Como o p-valor da estatística F ({format_p(modelo.f_pvalue)}) é maior ou igual a {alpha}, **não rejeitamos a hipótese nula global**."
            conclusao = "Não há evidências estatísticas suficientes para afirmar que existe diferença entre as médias dos grupos analisados."

        final_md = f"""
## 1. Resumo do Modelo
{resumo_md}

{hipoteses_md}

## 3. Tabela de Coeficientes
{coefs_md}

## 4. Diagnóstico dos Resíduos
{diag_md}

## 5. Decisão e Conclusão
{decisao_f}

**Conclusão:** {conclusao}
"""
        return Markdown(final_md)