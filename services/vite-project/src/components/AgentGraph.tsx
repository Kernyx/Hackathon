"use client";

import React, { useEffect, useRef } from 'react';
// Импортируем типы как типы, чтобы TS не ругался при verbatimModuleSyntax
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d';
import { toast } from 'sonner';
import { MOCK_AGENTS } from "@/lib/mockData"

// 1. Описываем интерфейсы более гибко, чтобы d3 (внутри графа) мог добавлять свои поля
interface AgentNode {
  id: string;
  name: string;
  img?: HTMLImageElement;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number;
  fy?: number;
}



interface AgentLink {
  source: string | AgentNode;
  target: string | AgentNode;
  message?: string;
}

interface GraphData {
  nodes: AgentNode[];
  links: AgentLink[];
}

interface AgentGraphProps {
  data: GraphData;
  onNodeSelect?: (node: AgentNode) => void;
}

const AgentGraph: React.FC<AgentGraphProps> = ({ data, onNodeSelect }) => {
  // ИСПРАВЛЕНИЕ: Убираем null из useRef и добавляем Any-генерики для совместимости с пропсом ref
  // Это фиксит ошибку: "Type 'RefObject' is not assignable to type 'MutableRefObject'"
  const graphRef = useRef<ForceGraphMethods<AgentNode, AgentLink>>(undefined);
    const graphData = {
    nodes: MOCK_AGENTS,
    links: [
        { source: '1', target: '2', message: 'Analyzing sentiment...' },
        { source: '1', target: '3', message: 'Sharing vector data' },
        { source: '2', target: '4', message: 'Requesting policy check' },
        { source: '3', target: '4', message: 'Encryption key exchange' },
        { source: '4', target: '5', message: 'Finalizing report' },
    ]
    };
  useEffect(() => {
    if (graphRef.current) {
      // Даем симуляции немного времени (200мс), чтобы раскидать узлы, 
      // а потом центрируем камеру по всем нодам
      setTimeout(() => {
        graphRef.current?.zoomToFit(400, 150); // 400мс анимация, 150px отступы
      }, 200);
    }
  }, [data]);
  // Кэширование изображений
  useEffect(() => {
    data.nodes.forEach(node => {
      if (!node.img) {
        const img = new Image();
        img.src = `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(node.name)}`;
        img.onload = () => {
          node.img = img;
        };
      }
    });
  }, [data.nodes]);

  const drawNode = (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const size = 5;
    const { x, y, name, img } = node;

    // Круг
    ctx.beginPath();
    ctx.arc(x, y, size, 0, 2 * Math.PI, false);
    ctx.fillStyle = '#6366f1'; 
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5 / globalScale;
    ctx.stroke();

    // Аватарка
    if (img && img.complete) {
      ctx.save();
      ctx.beginPath();
      ctx.arc(x, y, size - 0.5, 0, 2 * Math.PI, false);
      ctx.clip();
      ctx.drawImage(img, x - size, y - size, size * 2, size * 2);
      ctx.restore();
    }

    // Текст
    const fontSize = 12 / globalScale;
    ctx.font = `${fontSize}px Sans-Serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
    ctx.fillText(name, x, y + size + 2);
  };
const drawLinkCanvasObject = (link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const MAX_FONT_SIZE = 4;
    const LABEL_NODE_MARGIN = 6; // Отступ от узлов

    const start = link.source;
    const end = link.target;

    // Игнорируем, если это просто ID, а не объекты (d3 еще не проинициализировал их)
    if (typeof start !== 'object' || typeof end !== 'object') return;

    // Вычисляем среднюю точку
    const relLink = { x: end.x - start.x, y: end.y - start.y };
    const maxTextLength = Math.sqrt(Math.pow(relLink.x, 2) + Math.pow(relLink.y, 2)) - LABEL_NODE_MARGIN * 2;

    let textAngle = Math.atan2(relLink.y, relLink.x);
    // Переворачиваем текст, чтобы он не был вверх ногами
    if (textAngle > Math.PI / 2) textAngle = -(Math.PI - textAngle);
    if (textAngle < -Math.PI / 2) textAngle = -(-Math.PI - textAngle);

    const label = link.message || "";

    // Настройка шрифта
    const fontSize = MAX_FONT_SIZE / globalScale;
    ctx.font = `${fontSize}px monospace`;
    
    // Отрисовка
    ctx.save();
    ctx.translate(start.x + relLink.x / 2, start.y + relLink.y / 2); // Сдвигаемся в центр связи
    ctx.rotate(textAngle); // Поворачиваем по линии
    
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    ctx.fillStyle = 'rgba(99, 102, 241, 0.6)'; // Цвет индиго как у нод, но прозрачнее
    ctx.fillText(label, 0, -2); // Пишем текст чуть выше линии
    ctx.restore();
  };
  return (
    <div className="w-full h-[1000px]  rounded-xl overflow-hidden bg-transparent relative">
      <ForceGraph2D
        ref={graphRef}
        graphData={data}
        backgroundColor="rgba(0,0,0,0)"
        nodeCanvasObject={drawNode}
        // Указываем область захвата для курсора
        linkCanvasObject={drawLinkCanvasObject}
        linkCanvasObjectMode={() => 'after'}
        nodePointerAreaPaint={(node: any, color, ctx) => {
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(node.x, node.y, 14, 0, 2 * Math.PI, false);
          ctx.fill();
        }}
        onNodeClick={(node) => onNodeSelect?.(node as AgentNode)}
        
        linkColor={() => 'rgba(156, 163, 175, 0.3)'}
        linkDirectionalParticles={2}
        linkDirectionalParticleSpeed={0.005}
        linkDirectionalParticleWidth={2}
        
        onLinkClick={(link: any) => {
          // Обработка данных: d3 заменяет ID на объекты после инициализации
          const sourceName = typeof link.source === 'object' ? link.source.name : link.source;
          const targetName = typeof link.target === 'object' ? link.target.name : link.target;
          
          toast(`Установлен контакт: ${sourceName} -> ${targetName}`, {
            duration: 5000,
            position: 'bottom-right',
          });
        }}

        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
      />
    </div>
  );
};

export default AgentGraph;