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
    generator = PDFGenerator(font_family="'Arial', sans-serif", title_color="#000", title_text_align="center",
                             body_color="white",
                             text_color="#000", h2_color="#000", h3_color="#000", blockquote_border="#3498db",
                             table_header_bg="#2e86c1", page_margin="0.7in", image_max_width="80%",
                             add_page_numbers=True, font_path=None)

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

    with open('test_quiz.md', 'r', encoding='utf-8') as f:
        markdown_text = f.read()

    try:
        # Call get_customized_pdf_from_markdown method
        pdf_value = generator.get_customized_pdf_from_markdown(
            input_markdown=markdown_text,
            output_file="test_custom_pdf.pdf"
        )

        print(f"Successfully generated custom pdf from markdown")

    except Exception as e:
        logging.error(f"Error generating PDF: {e}")


if __name__ == "__main__":
    main()
