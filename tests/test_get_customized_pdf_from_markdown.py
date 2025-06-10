import os
import sys
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv(".env")

from polytext.generator.pdf import PDFGenerator

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def main():
    # Initialize PDFGenerator
    generator = PDFGenerator()
        # font_family="'Arial', sans-serif", title_color="#000", title_text_align="center",
        #                      body_color="white",
        #                      text_color="#000", h2_color="#000", h3_color="#000", blockquote_border="#3498db",
        #                      table_header_bg="#2e86c1", page_margin="0.7in", image_max_width="80%",
        #                      add_page_numbers=True, font_path=None)

    # Define Markdown content
#     markdown_text = """# Riassunto di Metodologia della ricerca sociale (Document Title)
# ## Il percorso della ricerca (Big Heading)
# Paragraph - Il percorso di una ricerca sociale è definito dal ricercatore, tenendo conto delle sue necessità, delle richieste del committente, dei vincoli esistenti e delle risorse disponibili. Nella ricerca sociale, le conclusioni devono essere supportate da "prove", ovvero dati che giustifichino le affermazioni del ricercatore.
# ### Ricerca empirica: tecniche, esempi e domande (Medium Heading)
# Kuhn ha schematizzato le fasi della scienza:\n
# - Fase 0: periodo pre-paradigmatico.\n
# - Fase 1: accettazione del paradigma.\n
# - Fase 2: scienza normale.\n
# - Fase 3: nascita delle anomalie.\n
# - Fase 4: crisi del paradigma.\n
# Il grado di libertà del ricercatore varia a seconda dell'argomento studiato. Ad esempio, studiare il tifo negli stadi offre maggiore libertà rispetto a studiare la violenza negli stadi. Tuttavia, una ricerca sulla violenza negli stadi ha un'utilità immediata maggiore, poiché mira a fornire indicazioni per intervenire sulla realtà e migliorarla, mentre una ricerca sul tifo negli stadi mira principalmente ad ampliare la conoscenza del fenomeno.\n
# **Ricerca standard o quantitativa (Small Heading)**\n
# Le risposte nella ricerca sociale devono essere documentate. Il ricercatore deve motivare le sue conclusioni con "prove", ovvero dati raccolti durante la ricerca che le supportino. Queste prove possono essere numeri (come i dati Istat) o testi (come le trascrizioni di interviste). A differenza di un investigatore che trova prove evidenti, il ricercatore sociale deve cercare "indizi" per arrivare alle risposte, partendo dalla definizione dei termini chiave (ad esempio, cosa definisce un tifoso o un disoccupato?).\n
# **Ricerca non standard o qualitativa**\n
# Nella ricerca sociale, l'applicazione di "regole metodologiche" è fondamentale per garantire il valore scientifico della ricerca.\n
# **Fasi della ricerca empirica**\n
# L'Istat raccoglie annualmente dati sulla povertà, presentati in tabelle basate su diverse
# caratteristiche delle famiglie povere. L'esplorazione del sito Istat può rivelare dati utili per
# una ricerca. Queste tabelle, corredate di commenti e schede metodologiche, forniscono
# informazioni, ad esempio, sulla maggiore incidenza della povertà nel Mezzogiorno. È
# possibile effettuare analisi longitudinali per studiare l'andamento del fenomeno nel tempo,
# scoprendo, ad esempio, che la povertà nel Mezzogiorno peggiora progressivamente.\n
# L'Istat raccoglie annualmente dati sulla povertà, presentati in tabelle basate su diverse
# caratteristiche delle famiglie povere. L'esplorazione del sito Istat può rivelare dati utili per
# una ricerca. Queste tabelle, corredate di commenti e schede metodologiche, forniscono
# informazioni, ad esempio, sulla maggiore incidenza della povertà nel Mezzogiorno. È
# possibile effettuare analisi longitudinali per studiare l'andamento del fenomeno nel tempo,
# scoprendo, ad esempio, che la povertà nel Mezzogiorno peggiora progressivamente.\n
# """
    markdown_text = """# 98 Domande con risposta su Etica e Scienze umane\n
**1. Come si distingue l’etica critica da un’etica basata sul senso comune o su preconcetti?**\n
L'etica critica si distingue per la sua capacità di sviluppare un pensiero autonomo, basato su principi razionali interiorizzati, permettendo di giustificare la propria posizione etica. Questo approccio si confronta con il diritto, la deontologia e l'etica personale, cercando un equilibrio tra norme, doveri professionali e valori individuali.\n
**2. In cosa consiste il principio del duplice effetto e quando è considerato eticamente accettabile?**\n
Il principio del duplice effetto si applica quando un'azione ha sia un effetto positivo che uno negativo. È eticamente accettabile se l'intenzione principale è ottenere il bene, il male è un effetto collaterale non intenzionale, e il bene non è ottenuto attraverso il male. Questo approccio si confronta con il diritto, la deontologia e l'etica personale, cercando un equilibrio tra norme, doveri professionali e valori individuali.\n
**3. Come si distingue l’etica critica da un’etica basata sul senso comune o su preconcetti?**\n
L'etica critica si distingue per la sua capacità di sviluppare un pensiero autonomo, basato su principi razionali interiorizzati, permettendo di giustificare la propria posizione etica. Questo approccio si confronta con il diritto, la deontologia e l'etica personale, cercando un equilibrio tra norme, doveri professionali e valori individuali. L'etica critica si distingue per la sua capacità di sviluppare un pensiero autonomo, basato su principi razionali interiorizzati, permettendo di giustificare la propria posizione etica. Questo approccio si confronta con il diritto, la deontologia e l'etica personale, cercando un equilibrio tra norme, doveri professionali e valori individuali.\n
**4. In cosa consiste il principio del duplice effetto e quando è considerato eticamente accettabile?**\n
Il principio del duplice effetto si applica quando un'azione ha sia un effetto positivo che uno negativo. È eticamente accettabile se l'intenzione principale è ottenere il bene, il male è un effetto collaterale non intenzionale, e il bene non è ottenuto attraverso il male.\n
**5. Come si distingue l’etica critica da un’etica basata sul senso comune o su preconcetti?**\n
L'etica critica si distingue per la sua capacità di sviluppare un pensiero autonomo, basato su principi razionali interiorizzati, permettendo di giustificare la propria posizione etica. Questo approccio si confronta con il diritto, la deontologia e l'etica personale, cercando un equilibrio tra norme, doveri professionali e valori individuali.\n
**6. In cosa consiste il principio del duplice effetto e quando è considerato eticamente accettabile?**\n
Il principio del duplice effetto si applica quando un'azione ha sia un effetto positivo che uno negativo. È eticamente accettabile se l'intenzione principale è ottenere il bene, il male è un effetto collaterale non intenzionale, e il bene non è ottenuto attraverso il male. Questo approccio si confronta con il diritto, la deontologia e l'etica personale, cercando un equilibrio tra norme, doveri professionali e valori individuali.\n
**7. Come si distingue l’etica critica da un’etica basata sul senso comune o su preconcetti?**\n
L'etica critica si distingue per la sua capacità di sviluppare un pensiero autonomo, basato su principi razionali interiorizzati, permettendo di giustificare la propria posizione etica. Questo approccio si confronta con il diritto, la deontologia e l'etica personale, cercando un equilibrio tra norme, doveri professionali e valori individuali. L'etica critica si distingue per la sua capacità di sviluppare un pensiero autonomo, basato su principi razionali interiorizzati, permettendo di giustificare la propria posizione etica. Questo approccio si confronta con il diritto, la deontologia e l'etica personale, cercando un equilibrio tra norme, doveri professionali e valori individuali.\n
"""

    markdown_text = """### Fattori che Influenzano il Numero di Cellule Somatiche (SCC)\nDiversi fattori possono aumentare l'SCC:\n\n *   Età: l'SCC aumenta con l'età, soprattutto dopo la quarta lattazione.\n*   Stadio di lattazione: l'SCC aumenta nell'ultima fase della lattazione (15-30 giorni).\n*   Stress: stress ambientali, alimentari o di gestione possono aumentare l'SCC.\n*   Stagione: alte temperature e umidità aumentano l'SCC.\n*   Ferite alla mammella: danni al tessuto mammario possono causare un aumento temporaneo dell'SCC.\n*   Cause indirette: mungitura inadeguata o manutenzione insufficiente dell'impianto di mungitura.\n\nIl normale livello di cellule somatiche dalla seconda lattazione in poi è minore o uguale a 200 mila \ncellule/ml di latte, nelle manze di primo parto è invece minore o uguale a 100 mila. Un innalzamento del livello di SCC è gravissimo soprattutto per il latte da caseificare, in quanto \ndetermina un aumento degli enzimi proteo e lipolitici, contenuti nei leucociti.\n\n### Linear Score (LS)\nIl Linear Score (LS) è un sistema di valutazione lineare da 1 a 9 per conteggi cellulari e implica il \nraddoppiamento del numero di cellule somatiche per ogni aumento di un punto nel LS. I vantaggi \nrispetto allo SCC sono:  \nminor variabilità di mese a mese nell'arco di una lattazione; \nereditabilità maggiore (il 25%) rispetto alla conta delle \ncellule somatiche; \nconsente di comparare vari allevamenti riguardo alla sanità \ndella mammella.\n\nScreening di massa considerano un problema bovine con LS ≥ 5, mentre \nmanze di prima lattazione dovrebbero presentare LS ≤ 3. L’obiettivo in un allevamento è avere il 90% delle bovine con un LS inferiore a 5.\n\n"""

    with open('test_quiz.md', 'r', encoding='utf-8') as f:
        markdown_text = f.read()

    try:
        # Call get_customized_pdf_from_markdown method
        pdf_value = generator.get_customized_pdf_from_markdown(
            input_markdown=markdown_text,
            output_file="test_custom_pdf.pdf",
            use_custom_css=True
        )

        print(f"Successfully generated custom pdf from markdown")

    except Exception as e:
        logging.error(f"Error generating PDF: {e}")


if __name__ == "__main__":
    main()
