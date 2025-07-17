import React, { useState, useRef, useCallback } from 'react';
import { Upload, Download, Eye, Settings, FileText, Shield, Check, AlertCircle, X, Edit2, RefreshCw, Zap } from 'lucide-react';

const DocumentAnonymizer = () => {
  const [step, setStep] = useState(1);
  const [uploadedFile, setUploadedFile] = useState(null);
  const [documentText, setDocumentText] = useState('');
  const [detectedData, setDetectedData] = useState([]);
  const [anonymizationMap, setAnonymizationMap] = useState({});
  const [isProcessing, setIsProcessing] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [showResults, setShowResults] = useState(false);
  const [anonymizedContent, setAnonymizedContent] = useState('');
  const [mapContent, setMapContent] = useState('');
  const [fileError, setFileError] = useState('');
  const [extractionLog, setExtractionLog] = useState([]);
  const [fileStats, setFileStats] = useState({});
  const fileInputRef = useRef(null);

  // Logging system pro debugging
  const addLog = (message, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    setExtractionLog(prev => [...prev, { timestamp, message, type }]);
    console.log(`[${timestamp}] ${type.toUpperCase()}: ${message}`);
  };

  // Validace kvality extrahovaného textu
  const validateTextQuality = (text, filename) => {
    const stats = {
      length: text.length,
      words: text.split(/\s+/).filter(word => word.length > 0).length,
      czechWords: (text.match(/[áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]/g) || []).length,
      numbers: (text.match(/\d/g) || []).length,
      specialChars: (text.match(/[^\w\s\n\r\táčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]/g) || []).length,
      lines: text.split('\n').length,
      readableRatio: 0
    };
    
    // Výpočet čitelnosti
    const readableChars = text.match(/[a-zA-ZáčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ\s\n\r\t.,;:!?()-]/g) || [];
    stats.readableRatio = stats.length > 0 ? (readableChars.length / stats.length) * 100 : 0;
    
    // Hodnocení kvality
    let quality = 'excellent';
    let issues = [];
    
    if (stats.length < 100) {
      quality = 'poor';
      issues.push('Příliš krátký text');
    } else if (stats.readableRatio < 70) {
      quality = 'poor';
      issues.push('Vysoký podíl nečitelných znaků');
    } else if (stats.words < 20) {
      quality = 'poor';
      issues.push('Nedostatek slov');
    } else if (stats.readableRatio < 85) {
      quality = 'fair';
      issues.push('Možné problémy s enkódováním');
    } else if (stats.words < 50) {
      quality = 'good';
      issues.push('Krátký obsah');
    }
    
    setFileStats(stats);
    addLog(`Kvalita textu: ${quality} (${stats.readableRatio.toFixed(1)}% čitelných znaků)`, 
      quality === 'poor' ? 'error' : quality === 'fair' ? 'warning' : 'success');
    
    if (issues.length > 0) {
      addLog(`Problémy: ${issues.join(', ')}`, 'warning');
    }
    
    return { quality, stats, issues };
  };

  // Vylepšená extrakce z DOCX s prioritizovanými metodami
  const extractTextFromDocx = async (file) => {
    addLog('Začínám extrakci z DOCX souboru', 'info');
    const methods = [];
    
    // Metoda 1: Mammoth.js (nejvyšší priorita)
    methods.push(async () => {
      addLog('Zkouším Mammoth.js', 'info');
      try {
        // Dynamický import
        const mammoth = await import('mammoth');
        const arrayBuffer = await file.arrayBuffer();
        const result = await mammoth.extractRawText({ arrayBuffer });
        
        if (result.value && result.value.trim().length > 50) {
          addLog(`Mammoth.js ÚSPĚCH: ${result.value.length} znaků`, 'success');
          return result.value.trim();
        }
        throw new Error('Mammoth vrátila prázdný výsledek');
      } catch (error) {
        addLog(`Mammoth.js selhala: ${error.message}`, 'error');
        throw error;
      }
    });

    // Metoda 2: Ruční XML parsing (střední priorita)
    methods.push(async () => {
      addLog('Zkouším ruční XML parsing', 'info');
      try {
        const arrayBuffer = await file.arrayBuffer();
        const uint8Array = new Uint8Array(arrayBuffer);
        
        // Konverze na string s UTF-8 podporou
        const decoder = new TextDecoder('utf-8', { fatal: false });
        const binaryString = decoder.decode(uint8Array);
        
        // Hledáme document.xml
        const docXmlMatches = binaryString.match(/word\/document\.xml.*?<w:document[^>]*>(.*?)<\/w:document>/s);
        
        if (docXmlMatches && docXmlMatches[1]) {
          const xmlContent = docXmlMatches[1];
          
          // Extrakce textu z <w:t> tagů s pokročilou regex
          const textMatches = xmlContent.match(/<w:t[^>]*>([^<]*)<\/w:t>/g) || [];
          
          const extractedText = textMatches
            .map(match => {
              const content = match.replace(/<w:t[^>]*>([^<]*)<\/w:t>/, '$1');
              return content;
            })
            .filter(text => text.trim().length > 0)
            .join(' ')
            .replace(/\s+/g, ' ')
            .trim();
          
          if (extractedText.length > 50) {
            addLog(`XML parsing ÚSPĚCH: ${extractedText.length} znaků`, 'success');
            return extractedText;
          }
        }
        
        throw new Error('Nenalezen validní XML obsah');
      } catch (error) {
        addLog(`XML parsing selhal: ${error.message}`, 'error');
        throw error;
      }
    });

    // Metoda 3: Zip + XML přístup (nejnižší priorita)
    methods.push(async () => {
      addLog('Zkouším ZIP + XML extrakci', 'info');
      try {
        const arrayBuffer = await file.arrayBuffer();
        const uint8Array = new Uint8Array(arrayBuffer);
        
        // Najdeme ZIP central directory
        const zipSignature = new Uint8Array([0x50, 0x4B, 0x03, 0x04]); // PK..
        let zipStart = -1;
        
        for (let i = 0; i < uint8Array.length - 4; i++) {
          if (uint8Array[i] === zipSignature[0] &&
              uint8Array[i + 1] === zipSignature[1] &&
              uint8Array[i + 2] === zipSignature[2] &&
              uint8Array[i + 3] === zipSignature[3]) {
            zipStart = i;
            break;
          }
        }
        
        if (zipStart === -1) {
          throw new Error('ZIP signatura nenalezena');
        }
        
        // Pokus o extrakci jakýchkoli čitelných sekvencí
        const decoder = new TextDecoder('utf-8', { fatal: false });
        const fullText = decoder.decode(uint8Array);
        
        // Hledáme XML tagy s textem
        const xmlTextMatches = fullText.match(/>([^<>{}\x00-\x1F]{10,})</g) || [];
        
        const meaningfulText = xmlTextMatches
          .map(match => match.slice(1, -1).trim())
          .filter(text => {
            // Filtrujeme jen smysluplný text
            return text.length > 5 && 
                   /[a-zA-ZáčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]/.test(text) &&
                   !/^[0-9.,-]+$/.test(text);
          })
          .join(' ')
          .replace(/\s+/g, ' ')
          .trim();
        
        if (meaningfulText.length > 100) {
          addLog(`ZIP extrakce ÚSPĚCH: ${meaningfulText.length} znaků`, 'success');
          return meaningfulText;
        }
        
        throw new Error('Nedostatek čitelného textu');
      } catch (error) {
        addLog(`ZIP extrakce selhala: ${error.message}`, 'error');
        throw error;
      }
    });

    // Postupné spouštění metod
    for (let i = 0; i < methods.length; i++) {
      try {
        const text = await methods[i]();
        const validation = validateTextQuality(text, file.name);
        
        if (validation.quality !== 'poor') {
          return text;
        } else {
          addLog(`Metoda ${i + 1} vrátila nekvalitní text, zkouším další`, 'warning');
        }
      } catch (error) {
        addLog(`Metoda ${i + 1} selhala: ${error.message}`, 'error');
        if (i === methods.length - 1) {
          throw new Error('Všechny metody extrakce selhaly. Zkuste uložit dokument jako .txt soubor.');
        }
      }
    }
  };

  // Funkce pro normalizaci jmen do základního tvaru
  const normalizePersonName = (name) => {
    const endings = {
      // Mužské jméno - 1. pád je základní
      'em': '',      // Janem → Jan
      'ovi': '',     // Janovi → Jan  
      'ův': '',      // Janův → Jan
      'u': '',       // Janu → Jan
      'e': '',       // Jane → Jan (5. pád)
      
      // Ženské jméno - základní tvar končí na -a
      'ě': 'a',      // Petře → Petra
      'ou': 'a',     // Petrou → Petra
      'y': 'a',      // Petry → Petra
      
      // Ženská příjmení - základní tvar končí na -ová
      'ové': 'ová',  // Svobodové → Svobodová
      'ovou': 'ová', // Svobodovou → Svobodová
      'ový': 'ová',  // Svobodový → Svobodová
      'ově': 'ová',  // Svobodově → Svobodová
      'ovu': 'ová',  // Svobodovu → Svobodová
      'ovy': 'ová',  // Svobodovy → Svobodová
      
      // Mužská příjmení - základní tvar
      'ák': 'ák',    // Novák → Novák
      'ákem': 'ák',  // Novákem → Novák
      'ákovi': 'ák', // Novákovi → Novák
      'áka': 'ák',   // Nováka → Novák
      'áku': 'ák',   // Nováku → Novák
      'áce': 'ák',   // Nováce → Novák
      'áky': 'ák',   // Nováky → Novák
    };
    
    const normalized = name.split(' ').map(word => {
      // Speciální pravidla pro časté ženské křestní jména
      if (['Petra', 'Jana', 'Anna', 'Eva', 'Marie', 'Kateřina', 'Tereza'].includes(word)) {
        return word; // Ženská křestní jména se nemění
      }
      
      // Zkusíme najít nejdelší vyhovující koncovku
      let bestMatch = { ending: '', replacement: word };
      
      for (const [ending, replacement] of Object.entries(endings)) {
        if (word.endsWith(ending) && word.length > ending.length && ending.length > bestMatch.ending.length) {
          bestMatch = { ending, replacement: word.slice(0, -ending.length) + replacement };
        }
      }
      
      return bestMatch.replacement;
    }).join(' ');
    
    return normalized;
  };

  // Funkce pro detekci citlivých dat v textu
  const detectSensitiveData = (text) => {
    addLog('Začínám detekci citlivých dat', 'info');
    const detectedItems = [];
    let idCounter = 1;
    
    // Regex patterns pro různé typy citlivých dat - v pořadí podle priority
    const patterns = [
      {
        // Bankovní účty (MUSÍ být první - specifičtější než telefony)
        regex: /\b\d{6,12}\/\d{4}\b/g,
        type: 'account',
        category: 'Bankovní účet'
      },
      {
        // Rodná čísla (MUSÍ být před telefony)
        regex: /\b\d{6}\/\d{3,4}\b/g,
        type: 'id',
        category: 'Rodné číslo'
      },
      {
        // Čísla občanských průkazů
        regex: /(?:Číslo OP:|OP:)\s*(\d{8,9})\b/g,
        type: 'op',
        category: 'Číslo OP'
      },
      {
        // Česká telefonní čísla
        regex: /\+420\s?\d{3}\s?\d{3}\s?\d{3}\b/g,
        type: 'phone',
        category: 'Telefon'
      },
      {
        // Jména osob - vylepšený pattern
        regex: /(?:^|\s)([A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][a-záčďéěíňóřšťúůýž]{2,}\s+[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][a-záčďéěíňóřšťúůýž]{2,})(?:\s|$|[^\w\s])/g,
        type: 'person',
        category: 'Jméno osoby',
        exclude: ['Na Hrázi', 'Květná', 'Škoda Octavia', 'Smluvní strany', 'Microsoft Word'],
        normalize: true,
        useGroup: 1
      },
      {
        // Emailové adresy
        regex: /\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b/g,
        type: 'email',
        category: 'Email'
      },
      {
        // IČO
        regex: /\bIČO:\s*\d{8}\b/g,
        type: 'ic',
        category: 'IČO'
      },
      {
        // Data narození
        regex: /\b\d{1,2}\.\s?\d{1,2}\.\s?\d{4}\b/g,
        type: 'date',
        category: 'Datum narození'
      },
      {
        // SPZ vozidla
        regex: /\b\d[A-Z]{2}\s?\d{4}\b|\b[A-Z]{2}\s?\d{3}\s?\d{2}\b/g,
        type: 'car',
        category: 'SPZ vozidla'
      },
      {
        // Adresy
        regex: /\b[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][a-záčďéěíňóřšťúůýž]+\s+\d+(?:\/\d+)?,\s*\d{3}\s?\d{2}\s+[A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][a-záčďéěíňóřšťúůýž]+/g,
        type: 'address',
        category: 'Adresa'
      }
    ];
    
    const usedPositions = new Set();
    
    patterns.forEach(pattern => {
      let match;
      while ((match = pattern.regex.exec(text)) !== null) {
        const matchedText = pattern.useGroup ? match[pattern.useGroup] : (match[1] || match[0]);
        const startPos = pattern.useGroup ? match.index + match[0].indexOf(match[pattern.useGroup]) : match.index;
        const endPos = startPos + matchedText.length;
        
        // Kontrola překrytí
        let hasOverlap = false;
        for (let i = startPos; i < endPos; i++) {
          if (usedPositions.has(i)) {
            hasOverlap = true;
            break;
          }
        }
        
        if (hasOverlap) continue;
        
        // Kontrola vyloučených termínů
        if (pattern.exclude && pattern.exclude.some(excluded => matchedText.includes(excluded))) {
          continue;
        }
        
        // Dodatečné filtry pro jména osob
        if (pattern.type === 'person') {
          if (/\d/.test(matchedText)) continue;
          if (matchedText.length < 6) continue;
          if (/ulice|náměstí|nám\.|ul\.|třída|sídliště/i.test(matchedText)) continue;
        }
        
        // Označit pozice jako použité
        for (let i = startPos; i < endPos; i++) {
          usedPositions.add(i);
        }
        
        // Pro jména normalizujeme do základního tvaru
        const normalizedText = pattern.normalize ? normalizePersonName(matchedText) : matchedText;
        
        detectedItems.push({
          id: idCounter++,
          type: pattern.type,
          text: matchedText,
          normalizedText: normalizedText,
          start: startPos,
          end: endPos,
          category: pattern.category
        });
      }
    });
    
    addLog(`Detekováno ${detectedItems.length} citlivých položek`, 'success');
    return detectedItems;
  };

  const handleFileUpload = useCallback(async (file) => {
    setUploadedFile(file);
    setIsProcessing(true);
    setFileError('');
    setExtractionLog([]);
    setDocumentText('');
    setDetectedData([]);
    setAnonymizationMap({});
    
    addLog(`Načítám soubor: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`, 'info');
    
    try {
      let text = '';
      
      if (file.name.toLowerCase().endsWith('.docx')) {
        text = await extractTextFromDocx(file);
      } else if (file.name.toLowerCase().endsWith('.txt')) {
        text = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = (e) => {
            addLog('TXT soubor úspěšně načten', 'success');
            resolve(e.target.result);
          };
          reader.onerror = reject;
          reader.readAsText(file, 'utf-8');
        });
      } else {
        throw new Error('Nepodporovaný formát souboru. Podporujeme .txt a .docx soubory.');
      }
      
      if (!text || text.length === 0) {
        throw new Error('Soubor je prázdný nebo neobsahuje čitelný text.');
      }
      
      // Validace kvality
      const validation = validateTextQuality(text, file.name);
      
      if (validation.quality === 'poor') {
        throw new Error(`Nekvalitní extrakce textu: ${validation.issues.join(', ')}`);
      }
      
      setDocumentText(text);
      
      // Detekce citlivých dat
      const detectedItems = detectSensitiveData(text);
      setDetectedData(detectedItems);
      generateAnonymizationMap(detectedItems);
      
      setFileError(`✅ Soubor "${file.name}" úspěšně zpracován (${text.length} znaků, kvalita: ${validation.quality})`);
      setIsProcessing(false);
      setStep(2);
      
    } catch (error) {
      addLog(`CHYBA: ${error.message}`, 'error');
      setFileError(`❌ ${error.message}`);
      setIsProcessing(false);
      // Nezměníme step, zůstaneme na uploadu
    }
  }, []);

  const generateAnonymizationMap = (data) => {
    const map = {};
    const counters = {};
    const normalizedGroups = {};
    
    const uniqueData = data.filter((item, index, self) => {
      return self.findIndex(other => 
        other.text === item.text && 
        other.start === item.start && 
        other.end === item.end
      ) === index;
    });
    
    const sortedData = [...uniqueData].sort((a, b) => {
      if (a.type === 'person' && b.type === 'person') {
        const normalizedA = a.normalizedText || a.text;
        const normalizedB = b.normalizedText || b.text;
        return normalizedA.localeCompare(normalizedB);
      }
      return 0;
    });
    
    sortedData.forEach(item => {
      let keyForMapping = item.text;
      
      if (item.type === 'person' && item.normalizedText) {
        if (normalizedGroups[item.normalizedText]) {
          map[item.text] = normalizedGroups[item.normalizedText];
          return;
        } else {
          keyForMapping = item.normalizedText;
        }
      }
      
      if (!counters[item.type]) {
        counters[item.type] = 1;
      }
      const code = item.type.toUpperCase() + '_' + String(counters[item.type]).padStart(3, '0');
      map[item.text] = code;
      
      if (item.type === 'person' && item.normalizedText) {
        normalizedGroups[item.normalizedText] = code;
      }
      
      counters[item.type]++;
    });
    
    setAnonymizationMap(map);
  };

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  }, [handleFileUpload]);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
  }, []);

  const toggleDataItem = (id) => {
    setDetectedData(prev => 
      prev.map(item => 
        item.id === id ? { ...item, excluded: !item.excluded } : item
      )
    );
  };

  const updateDataItem = (id, newText) => {
    setDetectedData(prev => 
      prev.map(item => 
        item.id === id ? { ...item, text: newText } : item
      )
    );
    setEditingItem(null);
  };

  const createAnonymizedDocument = () => {
    let anonymizedText = documentText;
    const finalMap = {};
    
    detectedData.forEach(item => {
      if (!item.excluded) {
        const code = anonymizationMap[item.text];
        if (code) {
          const escapedText = item.text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
          anonymizedText = anonymizedText.replace(new RegExp(escapedText, 'g'), code);
          finalMap[code] = item.text;
        }
      }
    });
    
    return { anonymizedText, finalMap };
  };

  const generateResults = () => {
    const { anonymizedText, finalMap } = createAnonymizedDocument();
    setAnonymizedContent(anonymizedText);
    setMapContent(JSON.stringify(finalMap, null, 2));
    setShowResults(true);
    setStep(4);
  };

  const copyToClipboard = async (text, type) => {
    try {
      await navigator.clipboard.writeText(text);
      alert(type + ' byl zkopírován do schránky!');
    } catch (err) {
      const textArea = document.createElement('textarea');
      textArea.value = text;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      alert(type + ' byl zkopírován do schránky!');
    }
  };

  const resetApp = () => {
    setStep(1);
    setUploadedFile(null);
    setDocumentText('');
    setDetectedData([]);
    setAnonymizationMap({});
    setIsProcessing(false);
    setShowResults(false);
    setAnonymizedContent('');
    setMapContent('');
    setEditingItem(null);
    setFileError('');
    setExtractionLog([]);
    setFileStats({});
  };

  const downloadAsFile = (content, filename, type = 'text/plain') => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-sm border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
                <Shield className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">DocAnonymizer Pro</h1>
                <p className="text-sm text-gray-600">Enterprise-grade anonymizace dokumentů</p>
              </div>
            </div>
            
            {/* Progress Steps */}
            <div className="flex items-center space-x-8">
              {[
                { num: 1, label: 'Upload', icon: Upload },
                { num: 2, label: 'Detekce', icon: Eye },
                { num: 3, label: 'Export', icon: Download },
                { num: 4, label: 'Hotovo', icon: Check }
              ].map(({ num, label, icon: Icon }) => (
                <div key={num} className="flex items-center space-x-2">
                  <div className={'w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ' + (
                    step >= num ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'
                  )}>
                    {step > num ? <Check className="w-4 h-4" /> : <Icon className="w-4 h-4" />}
                  </div>
                  <span className={'text-sm ' + (step >= num ? 'text-blue-600 font-medium' : 'text-gray-500')}>
                    {label}
                  </span>
                </div>
