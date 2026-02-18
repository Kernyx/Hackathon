"use client";

import React, { useEffect, useRef, useState } from 'react';
import ForceGraph2D, { type ForceGraphMethods, type NodeObject } from 'react-force-graph-2d';
import { getStoredAgents } from '@/lib/storage';

// Небольшой коэффициент масштаба под размер экрана
const getViewportScale = () => {
  if (typeof window === "undefined") return 1;
  const w = window.innerWidth;
  if (w < 640) return 0.9;        // мобильные — чуть компактнее
  if (w < 1024) return 1;         // планшеты / малые десктопы
  if (w < 1440) return 1.1;       // обычные десктопы
  return 1.2;                     // большие мониторы — чуть крупнее
};

interface AgentNode extends NodeObject {
  id: string;
  name: string;
  avatarSeed?: string;
  role?: string;
  img?: HTMLImageElement;
  val?: number;
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
  onNodeSelect?: (node: AgentNode) => void;
}

const AgentGraph: React.FC<AgentGraphProps> = ({ onNodeSelect }) => {
  const graphRef = useRef<ForceGraphMethods<AgentNode, AgentLink>>(undefined);
  const [data, setData] = useState<GraphData>({ nodes: [], links: [] });
  const [isMounted, setIsMounted] = useState(false);
  const [isEmpty, setIsEmpty] = useState(false);

  // Функция "выстрела" сообщением
  const emitMessage = (sourceId: string, targetId: string) => {
    if (!graphRef.current) return;
    
    const link = data.links.find(l => {
      const sId = typeof l.source === 'object' ? (l.source as any).id : l.source;
      const tId = typeof l.target === 'object' ? (l.target as any).id : l.target;
      return sId === sourceId && tId === targetId;
    });

    if (link) {
      // Ставим временный текст для визуала
      link.message = "DATA PACKET"; 
      graphRef.current.emitParticle(link);
      
      // Стираем текст через 2 секунды, чтобы не засирать экран
      setTimeout(() => { link.message = ""; }, 2000);
    }
  };

  // Интервал рандомных сообщений
  useEffect(() => {
    const interval = setInterval(() => {
      if (data.links.length > 0) {
        const randomLink = data.links[Math.floor(Math.random() * data.links.length)];
        const s = randomLink.source as AgentNode;
        const t = randomLink.target as AgentNode;

        if (s?.id && t?.id) {
          emitMessage(s.id, t.id);
        }
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [data]);

  // Загрузка данных
  useEffect(() => {
    setIsMounted(true);
    const agents = getStoredAgents();
    if (agents.length === 0) {
      setIsEmpty(true);
      return;
    }
    setIsEmpty(false);

    const nodes: AgentNode[] = agents
      .filter(agent => agent.id)
      .map(agent => ({
        id: agent.id!,
        name: agent.name || "Unknown",
        avatarSeed: agent.avatarSeed || agent.name,
        role: agent.role || "Agent",
        val: 1
      }));

    const links: AgentLink[] = [];
    if (nodes.length > 1) {
      for (let i = 0; i < nodes.length; i++) {
        const targetIndex = (i + 1) % nodes.length;
        links.push({
          source: nodes[i].id,
          target: nodes[targetIndex].id,
          message: ""
        });
      }
    }
    setData({ nodes, links });
  }, []);

  // Авто-зум
  useEffect(() => {
    if (graphRef.current && data.nodes.length > 0) {
      setTimeout(() => {
        graphRef.current?.zoomToFit(400, 300);
      }, 500);
    }
  }, [data]);

  // Длина рёбер (разлёт нод) в зависимости от количества агентов
  useEffect(() => {
    if (!graphRef.current || data.nodes.length === 0) return;
    const g = graphRef.current;
    const nodeCount = data.nodes.length;

    const linkForce = g.d3Force("link") as any;
    if (linkForce && typeof linkForce.distance === "function") {
      // Меньше агентов — больше длина рёбер, чтобы картинка была "воздушной".
      const base = nodeCount <= 3 ? 220 :
                   nodeCount <= 6 ? 180 :
                   nodeCount <= 12 ? 140 :
                   110;
      linkForce.distance(base);
      g.d3ReheatSimulation();
    }
  }, [data.nodes.length]);

  // Загрузка аватаров
  useEffect(() => {
    data.nodes.forEach(node => {
      if (!node.img) {
        const img = new Image();
        img.src = `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(node.avatarSeed || node.name)}`;
        img.onload = () => { node.img = img; };
      }
    });
  }, [data.nodes]);

  const drawNode = (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const viewportScale = getViewportScale();
    const baseSize = 12 * viewportScale;
    const size = baseSize;
    const { x, y, name, img } = node;
    
    // Тело узла
    ctx.beginPath();
    ctx.arc(x, y, size, 0, 2 * Math.PI, false);
    ctx.fillStyle = '#4f46e5';
    ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.9)';
    ctx.lineWidth = 2 / globalScale;
    ctx.stroke();

    // Аватар
    if (img && img.complete) {
      ctx.save();
      ctx.beginPath();
      ctx.arc(x, y, size - 1, 0, 2 * Math.PI, false);
      ctx.clip();
      ctx.drawImage(img, x - size, y - size, size * 2, size * 2);
      ctx.restore();
    }

    // Текст имени
    const fontSize = Math.max((14 * viewportScale) / globalScale, 7);
    ctx.font = `${fontSize}px Inter, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillStyle = 'rgba(243, 244, 246, 0.95)';
    ctx.fillText(name, x, y + size + 4 * viewportScale);
  };

  const drawLinkCanvasObject = (link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = link.message;
    if (!label) return;

    const viewportScale = getViewportScale();
    const nodeCount = data.nodes.length;

    // Прячем текст, когда граф сильно отдалён, чтобы не было каши.
    // Но для маленьких графов (<= 4 агента) всегда показываем.
    if (nodeCount > 4 && globalScale < 0.7) return;

    const start = link.source;
    const end = link.target;
    if (typeof start !== 'object' || typeof end !== 'object') return;

    // Вычисляем угол и центр
    const base = nodeCount <= 3 ? 18 : 14;
    const max = nodeCount <= 3 ? 22 : 18;
    const fontSize = Math.max(Math.min((base * viewportScale) / globalScale, max), 10);
    const relLink = { x: end.x - start.x, y: end.y - start.y };
    let textAngle = Math.atan2(relLink.y, relLink.x);
    if (textAngle > Math.PI / 2) textAngle = -(Math.PI - textAngle);
    if (textAngle < -Math.PI / 2) textAngle = -(-Math.PI - textAngle);

    ctx.save();
    // Переносим контекст в центр ребра
    ctx.translate(start.x + relLink.x / 2, start.y + relLink.y / 2);
    ctx.rotate(textAngle);

    ctx.font = `${fontSize}px monospace`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    ctx.fillStyle = 'rgba(129, 140, 248, 0.95)';
    
    // Рисуем текст в 0,0 (так как мы уже сделали translate)
    ctx.fillText(label, 0, -2);
    ctx.restore();
  };

  if (!isMounted) return null;

  if (isEmpty) {
    return (
      <div className="flex items-center justify-center h-full w-full">
        <div className="text-center text-muted-foreground">
          <p className="text-lg font-medium">No agents found</p>
          <p className="text-sm">Create some agents to see the graph</p>
        </div>
      </div>
    );
  }

  const nodeCountForLinks = data.nodes.length;
  return (
    <div className="w-full h-full min-h-150 rounded-xl overflow-hidde relative">
      <ForceGraph2D
        ref={graphRef}
        graphData={data}
        backgroundColor="rgba(0,0,0,0)"
        nodeCanvasObject={drawNode}
        linkCanvasObject={drawLinkCanvasObject}
        linkCanvasObjectMode={() => 'after'}
        
        // Физика
        d3AlphaDecay={0.03}
        d3VelocityDecay={0.3}
        cooldownTicks={100}
        
        // Связи и частицы
        linkColor={() => 'rgba(156, 163, 175, 0.2)'}
        linkWidth={(link) => {
          // Длина ребра управляется через силу "link". Здесь увеличиваем только
          // визуальную толщину чуть-чуть для малых графов.
          const count = nodeCountForLinks;
          if (count <= 3) return 3;
          if (count <= 7) return 2;
          return 1.2;
        }}
        linkDirectionalParticles={0}
        linkDirectionalParticleWidth={2.5}
        linkDirectionalParticleSpeed={0.01}
        linkDirectionalParticleColor={() => "#818cf8"}

        onNodeClick={(node) => onNodeSelect?.(node as AgentNode)}
      />
    </div>
  );
};

export default AgentGraph;