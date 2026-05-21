--
-- PostgreSQL database dump
--

\restrict Vxdk4heXlSZCQCsVHUIsXIesXjpgBq6WPO0k9I4oqFiDOGDhsXuPsWdBXoULjVe

-- Dumped from database version 16.13
-- Dumped by pg_dump version 16.13

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: acessos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.acessos (
    id integer NOT NULL,
    pessoa_id integer,
    data_entrada timestamp without time zone,
    data_saida timestamp without time zone
);


--
-- Name: acessos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.acessos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: acessos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.acessos_id_seq OWNED BY public.acessos.id;


--
-- Name: pessoas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pessoas (
    id integer NOT NULL,
    nome character varying(100),
    documento character varying(20),
    telefone character varying(20)
);


--
-- Name: pessoas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pessoas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pessoas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pessoas_id_seq OWNED BY public.pessoas.id;


--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios (
    id integer NOT NULL,
    username character varying(50),
    password character varying(200)
);


--
-- Name: usuarios_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usuarios_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuarios_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usuarios_id_seq OWNED BY public.usuarios.id;


--
-- Name: acessos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acessos ALTER COLUMN id SET DEFAULT nextval('public.acessos_id_seq'::regclass);


--
-- Name: pessoas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pessoas ALTER COLUMN id SET DEFAULT nextval('public.pessoas_id_seq'::regclass);


--
-- Name: usuarios id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios ALTER COLUMN id SET DEFAULT nextval('public.usuarios_id_seq'::regclass);


--
-- Data for Name: acessos; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.acessos (id, pessoa_id, data_entrada, data_saida) FROM stdin;
3	3	2026-03-30 16:38:45.047494	2026-03-30 16:38:48.430413
7	1	2026-03-30 16:38:52.929365	2026-03-30 16:38:53.827677
6	2	2026-03-30 16:38:52.025416	2026-03-30 16:38:54.33406
4	3	2026-03-30 16:38:49.689915	2026-03-30 16:38:55.328704
9	19	2026-03-30 17:00:24.275338	2026-03-30 17:00:27.455825
8	3	2026-03-30 17:00:20.158959	2026-03-30 17:00:28.156874
13	3	2026-03-30 17:05:39.906862	2026-03-30 17:26:33.179806
14	8	2026-03-30 17:05:40.445384	2026-03-30 17:26:33.61632
12	9	2026-03-30 17:05:39.401822	2026-03-30 17:26:34.373369
20	3	2026-03-30 17:26:36.644055	2026-03-30 17:26:38.583421
11	14	2026-03-30 17:05:39.129457	2026-04-28 17:40:56.335281
16	7	2026-03-30 17:05:41.471434	2026-04-28 17:40:58.313933
17	15	2026-03-30 17:05:41.826604	2026-04-28 17:41:03.661578
18	19	2026-03-30 17:05:43.274128	2026-04-28 17:41:04.139083
10	2	2026-03-30 17:05:22.305884	2026-04-28 17:41:04.871075
19	5	2026-03-30 17:05:47.505782	2026-04-28 17:41:05.334322
23	19	2026-04-28 17:51:23.769744	\N
24	20	2026-04-28 17:51:24.593802	\N
25	10	2026-04-28 17:51:24.925921	\N
26	15	2026-04-28 17:51:25.434342	\N
21	21	2026-04-28 17:41:27.022616	2026-04-28 18:05:09.389199
28	8	2026-04-28 18:05:07.245184	2026-04-28 18:05:10.142987
22	14	2026-04-28 17:51:23.040088	2026-04-28 18:05:11.046026
27	7	2026-04-28 17:51:25.787543	2026-04-28 18:05:11.851535
30	3	2026-04-28 18:19:34.017224	\N
\.


--
-- Data for Name: pessoas; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.pessoas (id, nome, documento, telefone) FROM stdin;
5	João Silva Santos	12345678901	81999990001
6	Maria Oliveira Costa	23456789012	81999990002
7	Carlos Henrique Souza	34567890123	81999990003
8	Ana Paula Fernandes	45678901234	81999990004
9	Bruno Ribeiro Alves	56789012345	81999990005
10	Fernanda Gomes Rocha	67890123456	81999990006
11	Ricardo Martins Lima	78901234567	81999990007
12	Juliana Barbosa Melo	89012345678	81999990008
13	Paulo Sérgio Carvalho	90123456789	81999990009
14	Camila Nunes Araújo	11223344556	81999990010
15	Diego Pereira Batista	22334455667	81999990011
16	Larissa Teixeira Cunha	33445566778	81999990012
17	Rafael Andrade Freitas	44556677889	81999990013
18	Patrícia Moraes Lopes	55667788990	81999990014
19	Eduardo Cardoso Pires	66778899001	81999990015
20	Fernando Sinesio	24242424	8192854238
21	Aluno1	1111111111	1111111111
22	Teste Pesso	1231	123123
1	Fulaninho de Tal	99991	781123121
2	Fernando Sinesio	242424242	123121513515
3	Alfredo	1212415123511	813109231231
\.


--
-- Data for Name: usuarios; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.usuarios (id, username, password) FROM stdin;
3	admin	scrypt:32768:8:1$gU0ixwYijAwgSfk1$52aeddd3bb8ff043f7744ca3b1d7806f599a5226fa29155413afaa3c209b2def009dfdaf44a9c2c49b4c3b0970d93aa409399d840d97e2cf70faf9912b7559db
\.


--
-- Name: acessos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.acessos_id_seq', 30, true);


--
-- Name: pessoas_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.pessoas_id_seq', 23, true);


--
-- Name: usuarios_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.usuarios_id_seq', 5, true);


--
-- Name: acessos acessos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acessos
    ADD CONSTRAINT acessos_pkey PRIMARY KEY (id);


--
-- Name: pessoas pessoas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pessoas
    ADD CONSTRAINT pessoas_pkey PRIMARY KEY (id);


--
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id);


--
-- Name: usuarios usuarios_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_username_key UNIQUE (username);


--
-- Name: acessos acessos_pessoa_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.acessos
    ADD CONSTRAINT acessos_pessoa_id_fkey FOREIGN KEY (pessoa_id) REFERENCES public.pessoas(id);


--
-- PostgreSQL database dump complete
--

\unrestrict Vxdk4heXlSZCQCsVHUIsXIesXjpgBq6WPO0k9I4oqFiDOGDhsXuPsWdBXoULjVe

